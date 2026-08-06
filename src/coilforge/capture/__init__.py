"""CoilForge capture ledger — append-only SQLite store of what each run produced.

Every coil selection generates (inputs -> machine proposal -> human correction).
That triple is the training signal for everything downstream (case retrieval,
review triage, per-rule reliability, rule induction) and it used to evaporate with
the HTTP response. This package persists it.

Review aid only: the ledger is a pure observer. It never touches export_allowed,
never stores raw customer bytes, and never breaks a request.
"""

from coilforge.capture.record import capture_milestone

__all__ = ["capture_milestone"]
