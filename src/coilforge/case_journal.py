"""PO Release Case journal writer (write-hook, v0).

Appends coil-workflow milestone events as JSONL lines to the shared PO Release
Case journal so the Case Reader / dashboard can track the coil ordering track
per project. Self-contained (stdlib only, no cross-repo imports); the line
format is the contract, documented in
PO_Release_Case\\schema\\journal_contract_v0.md.

Design rules:
- Append-only. Never reads, edits, or deletes existing journal lines.
- Best-effort. A journal failure must NEVER break a CoilForge request;
  record_coil_milestone returns an error string instead of raising.
- Coil tags (CDXC-1, HHWC-1, ...) travel in the VALUE, not identity.unit_tag -
  they are coil-level tags and must not become case units.
- CoilForge has no server-side store, so source_record points at the request
  milestone itself.
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime
from pathlib import Path

JOURNAL_VERSION = 0
SOURCE_TOOL = "coil"
DEFAULT_JOURNAL_DIR = (
    r"C:\Users\JohnKim\Desktop\Bins\Projects\PO_Release_Case\journal"
)
ENV_JOURNAL_DIR = "PO_RELEASE_CASE_JOURNAL_DIR"

MILESTONES = (
    "intake_draft",         # pdf-to-direct-draft completed
    "intake_drawing",       # pdf-to-drawing completed
    "package_assembled",    # drawing package generated
    "quote_package",        # quote package generated
    "checklist_filled",     # checklist Excel written (saved_path evidence)
    "direct_coil_verified", # direct-coil verify ran (match/mismatch counts)
)


def journal_dir() -> Path:
    return Path(os.environ.get(ENV_JOURNAL_DIR, "").strip() or DEFAULT_JOURNAL_DIR)


def record_coil_milestone(
    milestone: str,
    project_number: str | None,
    project_name: str | None,
    coil_tags: list[str] | None = None,
    detail: dict | None = None,
    note: str = "",
) -> str | None:
    """Append one coil milestone. Returns None on success, else an error string.

    Callers should skip the call when no project identity exists (demo/text
    paths); events without identity would only land in the reader's unmatched
    bucket.
    """
    if milestone not in MILESTONES:
        return f"unknown milestone: {milestone!r}"
    value = {"milestone": milestone, "coil_tags": list(coil_tags or [])}
    for key, item in (detail or {}).items():
        if key not in value:
            value[key] = item
    event = {
        "journal_version": JOURNAL_VERSION,
        "event_id": uuid.uuid4().hex,
        "ts": datetime.now().astimezone().isoformat(timespec="seconds"),
        "source_tool": SOURCE_TOOL,
        "identity": {
            "project_number": (str(project_number).strip() or None)
            if project_number else None,
            "project_name": (str(project_name).strip() or None)
            if project_name else None,
        },
        "source_record": {"table": "web_request", "pk": {"milestone": milestone}},
        "field": "coil_milestone",
        "value": value,
        "note": note or f"coil {milestone}",
    }
    try:
        target_dir = journal_dir()
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / f"coil-{datetime.now():%Y%m%d}.jsonl"
        with open(target, "a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
        return None
    except Exception as exc:  # best-effort: never break the request
        return f"case journal write failed: {exc}"
