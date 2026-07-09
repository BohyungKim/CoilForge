"""PO Release Case reader (case prefill deep link, v0).

READ-ONLY consumer of the Case Brain's derived views (cases\\PRC-<n>.json):
lets CoilForge open pre-analyzed on a case's submittal PDF instead of John
re-dropping the same file. Self-contained (stdlib only, no cross-repo
imports); the case JSON shape is the contract
(PO_Release_Case\\schema\\case_schema_v0.json - readers must ignore unknown
fields). Mirrors the BTOs reader (BOM Ordering Automation\\app\\lib\\case_brain.py).

Best-effort: a missing/corrupt case file returns None/[] and never raises
into the app.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

DEFAULT_CASES_DIR = (
    r"C:\Users\JohnKim\Desktop\Bins\Projects\PO_Release_Case\cases"
)
ENV_CASES_DIR = "PO_RELEASE_CASE_CASES_DIR"


def cases_dir() -> Path:
    return Path(os.environ.get(ENV_CASES_DIR, "").strip() or DEFAULT_CASES_DIR)


def is_safe_case_id(case_id: str) -> bool:
    """Reject path traversal (mirrors the Brain's own /api/cases guard)."""
    return bool(case_id) and not any(ch in case_id for ch in ("/", "\\", ".."))


def load_case(case_id: str) -> dict | None:
    if not is_safe_case_id(case_id):
        return None
    case_path = cases_dir() / f"{case_id}.json"
    try:
        with open(case_path, "r", encoding="utf-8") as f:
            case = json.load(f)
        return case if isinstance(case, dict) else None
    except Exception:
        return None


def case_identity(case: dict) -> dict:
    """{project_number, project_name, label "NNNN - Name"} from the case."""
    identity = case.get("identity", {}) if isinstance(case, dict) else {}
    number = identity.get("project_number")
    name = identity.get("project_name") or ""
    label = f"{number or ''} - {name}".strip(" -")
    return {
        "project_number": str(number) if number else None,
        "project_name": name or None,
        "label": label,
    }


def expected_coils(case: dict) -> list[dict]:
    """Latest coil_requirement journal event -> [{tag, qty, category}].
    The structured coils live only in events[]; status.tracks_suggested.coil
    carries pre-formatted display strings."""
    best_ts, best_coils = "", []
    for event in case.get("events", []) or []:
        if not isinstance(event, dict) or event.get("field") != "coil_requirement":
            continue
        value = event.get("value") or {}
        coils = value.get("coils") or []
        ts = str(event.get("ts") or "")
        if ts >= best_ts:
            best_ts, best_coils = ts, coils
    out = []
    for coil in best_coils:
        if isinstance(coil, dict) and coil.get("tag"):
            out.append({
                "tag": str(coil.get("tag")),
                "qty": coil.get("qty"),
                "category": str(coil.get("category") or ""),
            })
    return out


def find_submittal_pdf(case: dict) -> Path | None:
    """Locate the case's staged submittal PDF: journaled intake_path first,
    then intake\\<file_name>, then intake\\processed\\<file_name> (staged PDFs
    move to processed\\ after extraction - the fallback is load-bearing).
    Same chain as the Brain's own coil scan."""
    candidates: list[Path] = []
    intake_dir = cases_dir().parent / "intake"
    for event in reversed(case.get("events", []) or []):
        if not isinstance(event, dict) or event.get("field") != "intake_requested":
            continue
        value = event.get("value") or {}
        intake_path = str(value.get("intake_path") or "").strip()
        file_name = str(value.get("file_name") or "").strip()
        if intake_path:
            candidates.append(Path(intake_path))
        if file_name:
            candidates.append(intake_dir / file_name)
            candidates.append(intake_dir / "processed" / file_name)
    for path in candidates:
        try:
            if path.is_file():
                return path
        except OSError:
            continue
    return None
