"""Cross-check CCSI selection reports (filed in the PO folders) against CoilForge's CURRENT extraction.

The coil-data mapping's source of truth (John 2026-09-30): the CCSI report PDF each order folder
keeps under ``Accessory Order Forms/(DirectCoil/)<name>_REV<n>_<date>.pdf``. The highest REV is
the truth (the ordered state); a REV0 is the auxiliary original selection, compared so a value
changed at order time is told apart from a CoilForge mismatch. The CoilForge side is a fresh
extraction of that project's submittal with the current code, resolved through the same
``coil_data_sources`` the push payload uses.

Read-only over the PO folders. It never writes the capture ledger or the case journal — it imports
neither the web app nor the capture recorder, and runs with ``COILFORGE_CAPTURE=0`` besides. LLM
OCR is blocked unless ``--allow-ocr``: a submittal with unreadable pages is skipped as
``degraded_needs_ocr`` rather than compared half-read.

    python scripts/ccsi_report_crosscheck.py --projects 3154,3232,3237      # smoke
    python scripts/ccsi_report_crosscheck.py --workers 4                     # every project

``COILFORGE_PO_ROOT`` points at the "02 - POs" folder (default: the OneDrive SharePoint shortcut).
Outputs name customer projects, so they go to the gitignored ``outputs/ccsi_report_crosscheck/``.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import os
import re
import sqlite3
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from coilforge.capture.db import capture_db_path, code_version  # noqa: E402
from coilforge.ccsi import selection_report as sr  # noqa: E402
from coilforge.ccsi.coil_data_map import coil_data_sources, coil_type_for_tag  # noqa: E402
from coilforge.ccsi.crosscheck import crosscheck_coil  # noqa: E402
from coilforge.submittal.pdf_intake import coil_tag_aliases  # noqa: E402

OUT_DIR = ROOT / "outputs" / "ccsi_report_crosscheck"
CACHE_DIR = OUT_DIR / "cache"
DEFAULT_PO_ROOT = Path.home() / "OneDrive - Oxygen8" / "Oxygen8 SharePoint Shortcuts" / "Sales - Documents" / "02 - POs"
CATEGORIES = ("DX", "HGRH", "CWC", "HWC")
_OCR_BLOCKED_STATUS = "skipped_batch_no_ocr"


def _extraction_fingerprint() -> str:
    """Every source a cached extraction depends on, hashed ONCE at import.

    ``code_version()`` stays "<hash>-dirty" across uncommitted edits, so it cannot tell two dirty
    trees apart: an intake fix in the shared tree used to reuse the old extraction silently (the AA
    coating rule, 2026-09-30). Computed at import, not per call, so editing this runner mid-batch
    cannot file old-code results under a new key. NOT included: ``rules/*.yaml`` (an engine-rule
    edit would invalidate every extraction) — run with ``--refresh`` after one.
    """
    src = ROOT / "src" / "coilforge"
    files = [Path(__file__), src / "ccsi" / "coil_data_map.py"]
    for package in ("submittal", "direct_coil", "contracts", "corpus"):
        files += sorted((src / package).rglob("*.py"))
    digest = hashlib.sha256()
    for path in files:
        digest.update(path.relative_to(ROOT).as_posix().encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()[:12]


EXTRACTION_FINGERPRINT = _extraction_fingerprint()


# OneDrive placeholders: reading one downloads it. Local-only reads (2026-09-30): a cloud-only
# file is skipped and listed, never hydrated — downloads are a separate decision for John.
_CLOUD_ONLY_ATTRS = 0x400000 | 0x40000 | 0x1000  # RECALL_ON_DATA_ACCESS | RECALL_ON_OPEN | OFFLINE


def long_path(path: str | os.PathLike) -> str:
    """Windows extended-length form, so paths past 260 characters still open."""
    text = os.path.abspath(os.fspath(path))
    if os.name == "nt" and not text.startswith("\\\\?\\"):
        return "\\\\?\\" + text
    return text


def _is_cloud_only(entry: os.DirEntry) -> bool:
    # DirEntry.stat() on Windows comes from the directory listing — it does not open the file.
    return bool(getattr(entry.stat(follow_symlinks=False), "st_file_attributes", 0) & _CLOUD_ONLY_ATTRS)


def iter_pdfs(root: Path) -> list[tuple[Path, bool]]:
    """Every PDF under ``root`` as (path, cloud_only), without reading any file."""
    out: list[tuple[Path, bool]] = []
    stack = [long_path(root)]
    while stack:
        try:
            entries = list(os.scandir(stack.pop()))
        except OSError:
            continue
        for entry in entries:
            if entry.is_dir(follow_symlinks=False):
                stack.append(entry.path)
            elif entry.name.casefold().endswith(".pdf"):
                out.append((Path(entry.path.removeprefix("\\\\?\\")), _is_cloud_only(entry)))
    return sorted(out)


def install_ocr_guard() -> None:
    """Make every LLM OCR call a no-op for this process (and each worker)."""
    from coilforge.submittal import pdf_intake

    os.environ["OPENAI_API_KEY"] = ""

    def _blocked(_pdf_bytes: bytes, page_number: int):
        return pdf_intake._OcrPageResult(page_number=page_number, status=_OCR_BLOCKED_STATUS,
                                         error="LLM OCR is blocked in the report cross-check batch")

    pdf_intake._extract_page_text_with_llm_ocr_uncached = _blocked


# ------------------------------------------------------------------ CCSI reports
def scan_reports(project_dir: Path) -> dict[str, Any]:
    """Parse every candidate report of one project and pick the truth / REV0 files."""
    import fitz

    forms = project_dir / "Accessory Order Forms"
    file_skips: collections.Counter = collections.Counter()
    files: list[sr.ReportFile] = []
    records: dict[str, list[dict]] = {}
    cloud_only: list[str] = []
    if forms.is_dir():
        for path, is_cloud in iter_pdfs(forms):
            if not re.search(r"_REV\d", path.name, re.I):
                continue
            rel = path.relative_to(project_dir).as_posix()
            classified = sr.classify_report_path(rel)
            if isinstance(classified, str):
                file_skips[classified] += 1
                continue
            if is_cloud:
                file_skips["cloud_only"] += 1
                cloud_only.append(rel)
                continue
            rev, stem = classified
            try:
                data = Path(long_path(path)).read_bytes()
                pages = [page.get_text() for page in fitz.open(stream=data, filetype="pdf")]
            except Exception:  # noqa: BLE001 — a PDF we cannot open is counted, never guessed
                file_skips["open_failed"] += 1
                continue
            parsed = sr.parse_report_pages(pages)
            supported = [r for r in parsed if r["coil_type"]]
            file_skips.update(f.split(":")[0] for r in parsed for f in r["flags"] if f.startswith("unsupported_type"))
            date = next((r["date"] for r in supported if r["date"]), None)
            files.append(sr.ReportFile(rel_path=rel, rev=rev, stem=stem, sha256=hashlib.sha256(data).hexdigest(),
                                       date=_iso(date), coil_pages=len(supported)))
            records[rel] = supported
    picked = sr.pick_revisions(files)
    # A cloud-only report could be the higher REV, so a project with any is not judged locally.
    skip = picked["skip"] if files else "no_report"
    if cloud_only:
        skip = "cloud_only_reports"
    return {
        "truth_file": picked["truth"].rel_path if picked["truth"] else None,
        "rev0_file": picked["rev0"].rel_path if picked["rev0"] else None,
        "truth": records.get(picked["truth"].rel_path, []) if picked["truth"] else [],
        "rev0": records.get(picked["rev0"].rel_path, []) if picked["rev0"] else [],
        "kind": picked["kind"], "skip": skip, "file_skips": dict(file_skips), "cloud_only": cloud_only,
    }


def _iso(value: str | None):
    from datetime import datetime

    return datetime.fromisoformat(value) if value else None


# ------------------------------------------------------------------ submittal choice
_SUBMITTAL_EXCLUDE = re.compile(r"comments|\bold\b|as\s*-?built", re.I)
_SUBMITTAL_REV = re.compile(r"\brev\s*(\d+)([a-z]?)\b", re.I)


def ledger_hashes(conn: sqlite3.Connection | None, project_number: str) -> dict[str, str]:
    """{sha1 of an analysed submittal PDF: latest ts_utc} for the project's recorded runs."""
    if conn is None:
        return {}
    rows = conn.execute(
        "select input_hash, max(ts_utc) from run where ok = 1 and project_number = ? and input_hash is not null "
        "group by input_hash", (project_number,)).fetchall()
    return {h: ts for h, ts in rows}


def _sha1(path: Path) -> str:
    return hashlib.sha1(Path(long_path(path)).read_bytes()).hexdigest()


# The Oxygen8 cover: its Qty/Tag/Item/Model table and the footer "Version 1.0.0.x Project #NNNN / Rev #r".
_O8_COVER_FOOTER = re.compile(r"Version\s+1\.0\.0\.\d+\s+Project\s*#\s*(\d{3,5})", re.I)
# The revision is the cover's own "Revision No." field, NOT the footer's "Rev #": 3031's As-built prints
# footer "Rev #0" with "Revision No.: 2a", and 2814's footer wraps "#1_AsBuilt" onto another line.
_O8_COVER_REVISION = re.compile(r"Revision\s+No\.?\s*:\s*(\d+)?\s*([a-z])?(?![a-z])[\s_-]*(as[\s_-]*built)?", re.I)
_O8_COVER_HEADER = re.compile(r"Qty\s+Tag\s+Item\s+Model", re.I)
COVER_SCAN_PAGES = 20  # a signed copy leads with the engineer's review sheets (2982: cover on p.11)


def cover_revision_key(text: str) -> tuple[int, str, int]:
    """(number, letter, as_built) from the cover's "Revision No." — "2a" (2,'a',0), "1_AsBuilt" (1,'',1),
    "As built" (-1,'',1). As-built ranks above the same number; an unreadable field is (-1,'',0)."""
    match = _O8_COVER_REVISION.search(text)
    if not match:
        return -1, "", 0
    number, letter, as_built = match.groups()
    return (int(number) if number else -1), (letter or "").casefold(), (1 if as_built else 0)


def signed_cover(path: Path) -> tuple[str, tuple[int, str, int]] | None:
    """(project number, cover revision key) from the first Oxygen8 cover in ``path``'s first pages, else None."""
    try:
        import pdfplumber

        with pdfplumber.open(long_path(path)) as pdf:
            for page in pdf.pages[:COVER_SCAN_PAGES]:
                text = page.extract_text() or ""
                match = _O8_COVER_FOOTER.search(text)
                if match and _O8_COVER_HEADER.search(text):
                    return match.group(1), cover_revision_key(text)
    except Exception:  # noqa: BLE001 -- an unreadable file is simply not a cover
        return None
    return None


def _signed_final_by_cover(project_dir: Path, number: str) -> tuple[Path | None, str] | None:
    """John's rule "Signed Final over Final Working", by CONTENT (decision A, 2026-10-01).

    Signed copies are named by the engineer, not "Oxygen8 Submittal" (2982: "95 Berkely - ERVs REV0 - AAN
    (002).pdf"), so the name filter never saw them and the batch compared the superseded Rev0 (CDXC-2 LH
    where the As-built and the order say RH). A local Signed Final PDF counts when its own Oxygen8 cover
    names THIS project. Cloud-only files are never hydrated (on 2026-10-01 every cloud-only one was a
    ProductionRelease, and no local ProductionRelease carried a cover). Several covered files: an
    Oxygen8-named original beats every engineer copy — a stamp over the text can split numbers (2814's
    stamped copy read 2300 CFM as "2" and 58 F as "5") — and the engineer copy is used only when no
    original is filed (2982, 2541). Within that pool the highest cover "Revision No." wins (As-built above
    the same number). Still two different files -> skip, never guess. None = no covered file, the name
    rules decide as before."""
    signed = project_dir / "Signed Final Submittal"
    if not signed.is_dir():
        return None
    covered = []
    for path, cloud in iter_pdfs(signed):
        info = None if cloud else signed_cover(path)
        if info and info[0] == number:
            covered.append((info[1], path))
    if not covered:
        return None
    originals = [(rev, p) for rev, p in covered if "oxygen8 submittal" in p.name.casefold()]
    pool = originals or covered
    top_rev = max(rev for rev, _p in pool)
    top = [p for rev, p in pool if rev == top_rev]
    if len({_sha1(p) for p in top}) == 1:
        return top[0], "signed_final_cover"
    return None, "ambiguous_submittal"


def pick_submittal(project_dir: Path, hashes: dict[str, str], number: str | None = None) -> tuple[Path | None, str]:
    """(submittal PDF, how it was chosen) or (None, skip reason). Never guesses between ties and
    never reads a cloud-only file: when the right file might be one, the project is skipped.
    Order: ledger hash > Signed Final by cover (needs ``number``) > the name heuristic."""
    every_pdf = [(p, cloud) for sub in ("Final Working", "Signed Final Submittal") if (project_dir / sub).is_dir()
                 for p, cloud in iter_pdfs(project_dir / sub)]
    candidates = [(p, cloud) for p, cloud in every_pdf if "submittal" in p.name.casefold()]
    if hashes:
        # The ledger match is by sha1, so it needs no name filter — and a name filter here dropped the
        # very file CoilForge ran on whenever it was an engineer-named signed copy (2757, 2982, 3016, 3191
        # are LEDGER_MATCH in the submittal index but fell to the name heuristic here).
        found = []
        for path, cloud in every_pdf:
            if cloud:
                continue
            try:
                digest = _sha1(path)
            except OSError:
                continue
            if digest in hashes:
                found.append((hashes[digest], path))
        if found:
            found.sort()
            return found[-1][1], "ledger_hash"
    if number:
        by_cover = _signed_final_by_cover(project_dir, number)
        if by_cover is not None:
            return by_cover
    named = [(p, cloud) for p, cloud in candidates
             if "oxygen8 submittal" in p.name.casefold() and not _SUBMITTAL_EXCLUDE.search(p.name)]
    if not named:
        return None, "cloud_only_submittal" if any(cloud for _p, cloud in candidates) else "no_submittal"
    ranked = []
    for path, cloud in named:
        m = _SUBMITTAL_REV.search(path.stem)
        ranked.append(((int(m.group(1)), m.group(2).casefold()) if m else (-1, ""), path, cloud))
    ranked.sort(key=lambda item: item[0])
    top = [(p, cloud) for key, p, cloud in ranked if key == ranked[-1][0]]
    if any(cloud for _p, cloud in top):
        return None, "cloud_only_submittal"
    if len({_sha1(p) for p, _c in top}) > 1:
        return None, "ambiguous_submittal"
    return top[0][0], "heuristic_highest_rev"


# ------------------------------------------------------------------ CoilForge extraction
# Pages past the last cited coil page that still count as "inside the coil section": a trailing
# coil detail page that degraded would cite nothing, so it must not look like an appendix page.
_COIL_PAGE_MARGIN = 2


def coil_page_reach(candidates: list[Any], cover_page: int | None) -> int | None:
    """Last page the coil extraction depends on (cover + every cited evidence page, plus a margin);
    None when no coil evidence cites a page — then nothing proves a degraded page is irrelevant."""
    pages = {cover_page} if cover_page else set()
    for cand in candidates:
        dump = cand.model_dump() if hasattr(cand, "model_dump") else cand
        stack: list[Any] = [dump]
        while stack:
            node = stack.pop()
            if isinstance(node, dict):
                if isinstance(node.get("source_page"), int):
                    pages.add(node["source_page"])
                stack.extend(node.values())
            elif isinstance(node, list):
                stack.extend(node)
    return max(pages) + _COIL_PAGE_MARGIN if pages else None


def extract_submittal(pdf_path: str, allow_ocr: bool = False, refresh: bool = False) -> dict[str, Any]:
    """CoilForge's current coil-data sources for every coil of one submittal (cached)."""
    from coilforge.corpus.page_cache import intake_with_page_cache
    from coilforge.direct_coil import map_canonical_to_direct_coil_draft
    from coilforge.submittal.to_canonical import map_submittal_candidate_to_canonical_result

    data = Path(long_path(pdf_path)).read_bytes()
    key = f"{hashlib.sha256(data).hexdigest()[:24]}_{re.sub(r'[^A-Za-z0-9.-]', '_', code_version())}_{EXTRACTION_FINGERPRINT}"
    cache = CACHE_DIR / f"{key}.json"
    if cache.exists() and not refresh:
        return json.loads(cache.read_text(encoding="utf-8"))
    try:
        # Same intake, but the page text comes from the submittal page cache when it holds this
        # exact PDF (keyed by sha1): the pdfplumber pass is what made a full re-extraction take
        # hours (2026-09-30: 12 submittals in 54 min). A miss parses live and writes the cache.
        result = intake_with_page_cache(pdf_path, source_filename=Path(pdf_path).name).result
    except Exception as exc:  # noqa: BLE001 — reported per project, never fatal to the batch
        return {"skip": "intake_error", "error": f"{type(exc).__name__}: {exc}"[:300], "coils": []}
    degraded = sorted(result.summary.degraded_page_numbers)
    candidates = result.cover_candidates or [result.candidate]
    reach = coil_page_reach(candidates, result.summary.cover_page_number)
    if degraded and not allow_ocr and (reach is None or degraded[0] <= reach):
        out: dict[str, Any] = {"skip": "degraded_needs_ocr", "coils": [], "degraded_pages": degraded}
    else:
        coils = []
        for cand in candidates:
            tag = cand.tag.value if cand.tag is not None else None
            coil_type = coil_type_for_tag(str(tag)) if tag else None
            if coil_type is None:
                continue
            record = map_submittal_candidate_to_canonical_result(cand).record
            sources = coil_data_sources(cand, map_canonical_to_direct_coil_draft(record))
            coils.append({"tag": str(tag), "coil_type": coil_type,
                          "sources": {k: (v.model_dump(mode="json") if hasattr(v, "model_dump") else v)
                                      for k, v in sources.items()}})
        out = {"skip": None, "coils": coils}
        if degraded:
            out["degraded_pages_outside_coils"] = degraded
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(out, default=str), encoding="utf-8")
    return out


def _extract_job(args: tuple[str, bool, bool]) -> tuple[str, dict[str, Any]]:
    path, allow_ocr, refresh = args
    return path, extract_submittal(path, allow_ocr=allow_ocr, refresh=refresh)


# ------------------------------------------------------------------ matching + verdicts
def _aliases(tag: str | None) -> set[str]:
    return {a.upper() for a in coil_tag_aliases(tag)} if tag else set()


def pair_coils(left: list[dict], right: list[dict], left_tag: str, right_tag: str) -> list[tuple[dict, dict | None, str]]:
    """Pair each left coil with one right coil of the same type: by tag alias, else — only when the
    type has exactly one coil on each side — ``single_of_type``. Ambiguity pairs nothing."""
    out = []
    for coil in left:
        same_type = [r for r in right if r["coil_type"] == coil["coil_type"]]
        by_tag = [r for r in same_type if _aliases(coil.get(left_tag)) & _aliases(r.get(right_tag))]
        if len(by_tag) == 1:
            out.append((coil, by_tag[0], "tag"))
        elif len(by_tag) > 1:
            out.append((coil, None, "ambiguous_tag"))
        elif len(same_type) == 1 and sum(1 for c in left if c["coil_type"] == coil["coil_type"]) == 1:
            out.append((coil, same_type[0], "single_of_type"))
        else:
            out.append((coil, None, "no_tag_match"))
    return out


def _changed(a: Any, b: Any) -> bool:
    if a is None or b is None:
        return False
    x, y = sr.first_number(a), sr.first_number(b)
    if x is not None and y is not None and not re.search(r"[A-Za-z]", f"{a}{b}"):
        return abs(x - y) > 1e-9
    return sr.option_key(a) != sr.option_key(b)


def crosscheck_project(project: str, reports: dict[str, Any], submittal: dict[str, Any]) -> dict[str, Any]:
    usable = [r for r in reports["truth"] if not r["multi_tag"] and "parse_inconsistent" not in r["flags"]]
    skipped = collections.Counter(
        "multi_tag_selection" if r["multi_tag"] else "parse_inconsistent"
        for r in reports["truth"] if r not in usable)
    rev0_pairs = {id(t): r0 for t, r0, _m in pair_coils(usable, reports["rev0"], "base_tag", "base_tag") if r0}
    coils = []
    for truth, coil, method in pair_coils(usable, submittal["coils"], "base_tag", "tag"):
        if coil is None:
            skipped[method] += 1
            continue
        rows = crosscheck_coil(truth, coil["sources"], coil_type=truth["coil_type"])
        rev0 = rev0_pairs.get(id(truth))
        for row in rows:
            if rev0 is not None:
                before = (rev0["fields"].get(row["ccsi_id"]) or {}).get("value")
                row["changed_at_order"] = _changed(before, row["ccsi"])
                row["rev0"] = before
        coils.append({"project": project, "tag": truth["base_tag"], "coil_type": truth["coil_type"],
                      "match_method": method, "has_rev0": rev0 is not None, "rows": rows,
                      "report_flags": truth["flags"], "unmapped_labels": sorted(truth["unmapped_labels"])})
    return {"coils": coils, "skipped_coils": dict(skipped)}


# ------------------------------------------------------------------ aggregation + output
def aggregate(results: list[dict[str, Any]]) -> dict[str, Any]:
    """Per category and CCSI field: how many PROJECTS land in each verdict, split by reason code."""
    by_cat: dict[str, Any] = {c: {"coils": 0, "projects": set(), "fields": collections.defaultdict(
        lambda: collections.defaultdict(set)), "rows": []} for c in CATEGORIES}
    for res in results:
        for coil in res.get("coils", []):
            cat = by_cat.get(coil["coil_type"])
            if cat is None:
                continue
            cat["coils"] += 1
            cat["projects"].add(coil["project"])
            for row in coil["rows"]:
                if row["ccsi_id"] == "Tag":
                    continue  # the join key, not a compared field
                verdict = "not_on_report" if row["verdict"] == "absent_on_form" else row["verdict"]
                bucket = f"{verdict}" + (f" [{row['reason_code']}]" if row.get("reason_code") in (
                    "CCSI_DEFAULT_PROFILE", "CCSI_GEOMETRY_RESELECT") else "")
                if row.get("changed_at_order") and verdict == "mismatch":
                    bucket += " (changed at order)"
                cat["fields"][row["ccsi_id"]][bucket].add(coil["project"])
                if verdict not in ("match", "both_missing", "not_on_report", "not_persisted"):
                    cat["rows"].append({"project": coil["project"], "tag": coil["tag"], **row})
    return {c: {"coils": v["coils"], "projects": len(v["projects"]),
                "fields": {f: {b: len(p) for b, p in sorted(bs.items())} for f, bs in sorted(v["fields"].items())},
                "rows": v["rows"]} for c, v in by_cat.items()}


def render_markdown(category: str, data: dict[str, Any]) -> str:
    lines = [f"# CCSI selection report vs CoilForge — {category}", "",
             f"{data['coils']} coils in {data['projects']} projects. Counts are PROJECTS per verdict.", "",
             "| CCSI field | verdicts (projects) |", "|---|---|"]
    for field, buckets in data["fields"].items():
        lines.append(f"| `{field}` | " + ", ".join(f"{b} {n}" for b, n in buckets.items()) + " |")
    lines += ["", "## Non-matching values", "", "| project | coil | field | verdict | CoilForge | CCSI report | REV0 | reason |",
              "|---|---|---|---|---|---|---|---|"]
    for r in data["rows"]:
        lines.append(f"| {r['project']} | {r['tag']} | `{r['ccsi_id']}` | {r['verdict']}"
                     f"{' (changed at order)' if r.get('changed_at_order') else ''} | {r['coilforge']!r} | {r['ccsi']!r} | "
                     f"{r.get('rev0')!r} | {r.get('reason_code') or ''} |")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--projects", help="comma-separated project numbers (default: every project)")
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--allow-ocr", action="store_true", help="let intake call LLM OCR on unreadable pages")
    parser.add_argument("--refresh", action="store_true", help="ignore the extraction cache")
    args = parser.parse_args()
    # Second guard (this script imports no capture writer). Set here, not at import: importing the
    # module must not switch capture off for a whole test process; the worker pool inherits it.
    os.environ["COILFORGE_CAPTURE"] = "0"
    if not args.allow_ocr:
        install_ocr_guard()
    po_root = Path(os.environ.get("COILFORGE_PO_ROOT") or DEFAULT_PO_ROOT)
    wanted = {p.strip() for p in args.projects.split(",")} if args.projects else None
    projects = sorted(p for p in po_root.iterdir() if p.is_dir() and re.match(r"^\d{4}\b", p.name)
                      and (wanted is None or p.name[:4] in wanted))
    try:
        conn: sqlite3.Connection | None = sqlite3.connect(f"file:{capture_db_path()}?mode=ro", uri=True)
    except sqlite3.Error:
        conn = None
    plan, skips = [], collections.Counter()
    cloud_only: dict[str, dict[str, Any]] = {}  # what a later, approved download would unlock
    for project_dir in projects:
        number = project_dir.name[:4]
        reports = scan_reports(project_dir)
        if reports["cloud_only"]:
            cloud_only.setdefault(number, {})["reports"] = reports["cloud_only"]
        if reports["skip"]:
            skips[f"report:{reports['skip']}"] += 1
            continue
        submittal, how = pick_submittal(project_dir, ledger_hashes(conn, number), number)
        if submittal is None:
            if how == "cloud_only_submittal":
                cloud_only.setdefault(number, {})["submittal"] = True
            skips[f"submittal:{how}"] += 1
            continue
        plan.append((number, reports, submittal, how))
        print(f"{number}: truth {reports['truth_file']} ({reports['kind']}) · submittal via {how}", flush=True)
    if conn is not None:
        conn.close()
    jobs = sorted({(str(s), args.allow_ocr, args.refresh) for _n, _r, s, _h in plan})
    if args.workers > 1:
        initializer = None if args.allow_ocr else install_ocr_guard
        with ProcessPoolExecutor(max_workers=args.workers, initializer=initializer) as pool:
            extracted = dict(pool.map(_extract_job, jobs))
    else:
        extracted = dict(_extract_job(job) for job in jobs)
    results = []
    for number, reports, submittal, how in plan:
        ext = extracted[str(submittal)]
        if ext.get("skip"):
            skips[f"submittal:{ext['skip']}"] += 1
            continue
        res = crosscheck_project(number, reports, ext)
        res.update({"project": number, "report_kind": reports["kind"], "truth_file": reports["truth_file"],
                    "rev0_file": reports["rev0_file"], "submittal": Path(submittal).name, "submittal_pick": how,
                    "degraded_pages_outside_coils": ext.get("degraded_pages_outside_coils", [])})
        results.append(res)
    summary = aggregate(results)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "crosscheck.json").write_text(json.dumps(
        {"code_version": code_version(), "projects_compared": len(results), "skips": dict(skips),
         "cloud_only": cloud_only, "summary": summary, "projects": results}, indent=2, default=str), encoding="utf-8")
    for category in CATEGORIES:
        if summary[category]["coils"]:
            (OUT_DIR / f"{category.lower()}.md").write_text(render_markdown(category, summary[category]), encoding="utf-8")
    print(f"compared {len(results)} projects; skips: {dict(skips)}")
    for category in CATEGORIES:
        print(f"  {category}: {summary[category]['coils']} coils / {summary[category]['projects']} projects")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
