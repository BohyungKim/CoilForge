"""Suite-wide isolation for the capture ledger.

The ledger hooks ``_journal_milestone``, so ANY test that drives a milestone route
writes to it. Without this the suite silently files fixture coils into John's real
ML corpus (~19 runs of test data per run of the suite), and a corpus you cannot
trust is worse than no corpus — you would only find out months later, at the point
of training. Autouse + session scope: no test file has to remember.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest  # noqa: E402


@pytest.fixture(autouse=True, scope="session")
def _isolate_capture_ledger(tmp_path_factory):
    from coilforge.capture import db

    ledger = tmp_path_factory.mktemp("capture") / "test-ledger.sqlite3"
    previous = os.environ.get(db.ENV_CAPTURE_DB)
    os.environ[db.ENV_CAPTURE_DB] = str(ledger)
    try:
        yield ledger
    finally:
        if previous is None:
            os.environ.pop(db.ENV_CAPTURE_DB, None)
        else:
            os.environ[db.ENV_CAPTURE_DB] = previous
