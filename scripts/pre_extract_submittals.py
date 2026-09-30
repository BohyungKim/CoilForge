"""Pre-extract submittal page text into the on-disk cache (``coilforge.corpus.page_cache``).

Scope (John 2026-09-30): the PDFs the capture ledger has seen, plus the primary
submittal of each ``--project``, plus explicit ``--path`` / ``--assign`` files.

    python scripts/pre_extract_submittals.py --ledger-matches --project 3031 --project 3232 --dry-run
    python scripts/pre_extract_submittals.py --assign 3232="C:\\...\\3232 - E-One Plant 4.pdf" --dry-run
    python scripts/pre_extract_submittals.py --ledger-matches --project 3031 --project 3232

``--dry-run`` downloads nothing: it hashes LOCAL candidates only, prints the per-project
primary table (reason, provisional, rejected files) and the download/time estimate, and
writes ``primaries.json``. Stop there and have John approve before the real run -- the
real run downloads cloud-only files (one at a time) and extracts in worker processes.

The ledger path is never an argument (``ledger_link.ledger_path``: env or constant).
Build the index first: ``python scripts/build_submittal_index.py``.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from coilforge.corpus.fs import is_cloud_only, long_path, read_pdf_bytes, resolve_data_dir  # noqa: E402
from coilforge.corpus.ledger_link import (  # noqa: E402
    Assignment,
    LedgerState,
    PrimarySelection,
    ledger_candidates,
    ledger_path,
    load_assignments,
    load_ledger_pdfs,
    select_primary,
    write_assignments,
    write_primaries,
)
from coilforge.corpus.page_cache import BatchItem, read_page_record, run_batch  # noqa: E402
from coilforge.corpus.submittal_index import entries_for_project, load_index  # noqa: E402

# Measured 2026-09-30 on 8 real submittals: 0.5-13.6 min live, mean ~4.2 min.
MINUTES_PER_PDF = 4.0


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _currently_cloud_only(path: str) -> bool:
    try:
        return is_cloud_only(getattr(os.stat(long_path(path)), "st_file_attributes", 0))
    except OSError:
        return True


def _print_selection(selection: PrimarySelection, *, detailed: bool) -> None:
    flags = []
    if selection.provisional:
        flags.append("provisional")
    if selection.duplicate_folder_number:
        flags.append("duplicate-folder-number")
    marker = "FAIL-CLOSED" if selection.fail_closed else ("usable" if selection.usable else "HOLD")
    name = Path(selection.primary_path).name if selection.primary_path else "-"
    print(f"  {selection.project:>6}  {marker:<11} {selection.reason:<26} {name}  {' '.join(flags)}")
    if detailed:
        if selection.primary_path:
            print(f"          primary: {selection.primary_path}")
        for copy in selection.copies:
            print(f"          copy:    {copy}")
        for rejected in selection.rejected:
            print(f"          reject:  {rejected.reason:<18} {rejected.path}")


def main(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--ledger-matches", action="store_true", help="extract every ledger-seen PDF found in the index")
    parser.add_argument("--project", action="append", default=[], help="project whose primary is extracted (repeatable)")
    parser.add_argument("--path", action="append", default=[], help="extra absolute PDF path (repeatable)")
    parser.add_argument("--assign", action="append", default=[], help="PROJECT=PATH: John's pick, saved to assignments.json")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--timeout-min", type=float, default=20.0)
    parser.add_argument("--max-hydrate", type=int, default=None, help="max cloud-only files to download this run")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--index-dir", default=None)
    args = parser.parse_args(argv)

    data_dir = resolve_data_dir(args.index_dir)
    index = load_index(data_dir)
    entry_by_path = {entry.path: entry for entry in index.entries}
    ledger = load_ledger_pdfs(ledger_path())
    candidates = ledger_candidates(index, ledger)
    cand_by_path: dict[str, set[str]] = collections.defaultdict(set)
    for sha1, entries in candidates.items():
        for entry in entries:
            cand_by_path[entry.path].add(sha1)

    # Hash LOCAL files only (no download): ledger candidates + every file of --project.
    state = LedgerState(ledger=ledger)
    scoped = {entry.path for project in args.project for entry in entries_for_project(index, project)}
    local_mismatch = 0
    for path in sorted(set(cand_by_path) | scoped):
        if entry_by_path[path].cloud_only_at_scan or _currently_cloud_only(path):
            if path in cand_by_path:
                state.provisional.add(path)
            continue
        try:
            sha1 = hashlib.sha1(read_pdf_bytes(path)).hexdigest()
        except OSError as exc:
            print(f"read failed (local): {path}: {exc!r}")
            continue
        state.file_sha1[path] = sha1
        if path in cand_by_path:
            if sha1 in cand_by_path[path]:
                state.confirmed[path] = sha1
            else:
                local_mismatch += 1

    assignments = load_assignments(data_dir)
    for spec in args.assign:
        project, sep, raw_path = spec.partition("=")
        if not sep or not project.strip() or not raw_path.strip():
            parser.error(f"--assign expects PROJECT=PATH, got {spec!r}")
        path = os.path.abspath(raw_path.strip().strip('"'))
        if path not in entry_by_path:
            print(f"note: assigned file is not in the index: {path}")
        try:
            sha1 = hashlib.sha1(read_pdf_bytes(path)).hexdigest()
        except OSError as exc:
            parser.error(f"--assign cannot read {path}: {exc}")
        state.file_sha1[path] = sha1
        assignments[project.strip()] = Assignment(project=project.strip(), path=path, sha1=sha1, assigned_at=_now())
    if args.assign:
        write_assignments(assignments, data_dir)

    table_projects = sorted(
        set(args.project)
        | {entry_by_path[path].project_number for path in cand_by_path if entry_by_path[path].project_number}
        | set(assignments)
    )

    def select_all() -> dict[str, PrimarySelection]:
        return {
            project: select_primary(project, entries_for_project(index, project), state, assignments.get(project))
            for project in table_projects
        }

    selections = select_all()

    items: list[BatchItem] = []
    queued: set[str] = set()

    def queue(path: str, ledger_expected: set[str] | None = None) -> None:
        if path in queued:
            return
        queued.add(path)
        entry = entry_by_path.get(path)
        cloud = (entry.cloud_only_at_scan if entry else _currently_cloud_only(path)) and path not in state.file_sha1
        items.append(BatchItem(path=path, cloud_only=cloud, ledger_expected=ledger_expected))

    if args.ledger_matches:
        for path, sha1s in sorted(cand_by_path.items()):
            if path in state.confirmed or path in state.provisional:
                queue(path, set(sha1s))
    for project in args.project:
        selection = selections[project]
        if selection.primary_path and not selection.provisional:
            queue(selection.primary_path)
    for selection in selections.values():
        if selection.reason == "JOHN_ASSIGNED" and selection.primary_path:
            queue(selection.primary_path)
    for raw in args.path:
        queue(os.path.abspath(raw))

    # --- report -------------------------------------------------------------------------
    confirmed_sha1s = set(state.confirmed.values())
    provisional_sha1s = {sha1 for path in state.provisional for sha1 in cand_by_path[path]}
    not_found = sorted(sha1 for sha1 in ledger if sha1 not in confirmed_sha1s and sha1 not in provisional_sha1s)
    already_cached = sum(
        1 for item in items
        if item.path in state.file_sha1 and read_page_record(data_dir, state.file_sha1[item.path])[0] == "HIT"
    )
    cloud_items = [item for item in items if item.cloud_only]
    cloud_bytes = sum(entry_by_path[item.path].size for item in cloud_items if item.path in entry_by_path)
    to_extract = len(items) - already_cached
    hours = to_extract * MINUTES_PER_PDF / max(1, args.workers) / 60

    print(f"ledger PDFs: {len(ledger)}  confirmed locally: {len(confirmed_sha1s)}  "
          f"provisional (cloud-only candidates): {len(provisional_sha1s)}  not found: {len(not_found)}  "
          f"local size-only mismatches: {local_mismatch}")
    print(f"primary table ({len(selections)} projects; detailed for --project / --assign):")
    detailed = set(args.project) | {spec.partition("=")[0].strip() for spec in args.assign}
    for project, selection in selections.items():
        _print_selection(selection, detailed=project in detailed)
    fail_closed = [p for p, s in selections.items() if s.fail_closed and p in detailed]
    print(f"to process: {len(items)} files ({already_cached} already cached)  "
          f"cloud-only downloads: {len(cloud_items)} ({cloud_bytes / 1e9:.2f} GB)  "
          f"estimate: ~{hours:.1f} h at {args.workers} workers")
    if fail_closed:
        print("needs John (--assign PROJECT=PATH): " + ", ".join(fail_closed))
    if not_found:
        print("ledger PDFs not found in the index (uploaded from outside the PO tree?): "
              + ", ".join(sha1[:10] for sha1 in not_found[:40]) + (" …" if len(not_found) > 40 else ""))

    if args.dry_run:
        target = write_primaries(selections.values(), data_dir)
        print(f"dry run: nothing downloaded or extracted. primaries: {target}")
        return 0

    # --- run ----------------------------------------------------------------------------
    runs_dir = data_dir / "runs"
    os.makedirs(long_path(runs_dir), exist_ok=True)
    log_path = runs_dir / f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.jsonl"
    counts: collections.Counter[str] = collections.Counter()
    with open(long_path(log_path), "a", encoding="utf-8") as log:
        def emit(event: dict) -> None:
            counts[event["status"]] += 1
            log.write(json.dumps(event, ensure_ascii=True) + "\n")
            log.flush()
            print(f"[{event['status']}] {Path(event['path']).name}", flush=True)

        outcome = run_batch(
            items, data_dir=data_dir, workers=args.workers, timeout_s=args.timeout_min * 60,
            max_hydrate=args.max_hydrate, emit=emit,
        )
        state.file_sha1.update(outcome.file_sha1)
        state.confirmed.update(outcome.ledger_confirmed)
        state.provisional -= set(outcome.file_sha1)
        before = selections
        selections = select_all()
        for project, selection in selections.items():
            if selection.primary_path != before[project].primary_path and selection.reason != "JOHN_ASSIGNED":
                # John approved the dry-run table, not this file: hold it back.
                selection.provisional = True
                emit({"ts": _now(), "status": "PRIMARY_CHANGED_UNAPPROVED", "path": selection.primary_path or "-",
                      "sha1": selection.primary_sha1, "project": project,
                      "previous": before[project].primary_path, "reason": selection.reason})

    target = write_primaries(selections.values(), data_dir)
    print(f"done. {dict(sorted(counts.items()))}  aborted={outcome.aborted}")
    print(f"log: {log_path}\nprimaries: {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
