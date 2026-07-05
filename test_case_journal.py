"""Standalone check for src/coilforge/case_journal.py (run: python test_case_journal.py).

Writes to a TEMP journal dir via the PO_RELEASE_CASE_JOURNAL_DIR override -
the real journal is never touched.
"""

import json
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

with tempfile.TemporaryDirectory(prefix="case_journal_test_") as tmp:
    os.environ["PO_RELEASE_CASE_JOURNAL_DIR"] = tmp

    from coilforge.case_journal import record_coil_milestone

    err = record_coil_milestone(
        "checklist_filled",
        project_number="3023",
        project_name="Kenton Elementary",
        coil_tags=["CDXC-1", "RHHGRC-1"],
        detail={"saved_path": r"C:\Users\x\Downloads\3023 - Coil Checklist.xlsx",
                "coils": 2},
    )
    assert err is None, err
    assert "unknown milestone" in record_coil_milestone("launched", "3023", "X")

    target = Path(tmp) / f"coil-{datetime.now():%Y%m%d}.jsonl"
    event = json.loads(target.read_text(encoding="utf-8").splitlines()[0])
    assert event["source_tool"] == "coil"
    assert event["field"] == "coil_milestone"
    assert event["identity"] == {"project_number": "3023",
                                 "project_name": "Kenton Elementary"}
    value = event["value"]
    assert value["milestone"] == "checklist_filled"
    assert value["coil_tags"] == ["CDXC-1", "RHHGRC-1"]
    assert value["saved_path"].endswith("Coil Checklist.xlsx")
    assert event["source_record"] == {"table": "web_request",
                                      "pk": {"milestone": "checklist_filled"}}

print("case_journal standalone check: PASSED")
