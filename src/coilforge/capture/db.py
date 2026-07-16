"""Capture-ledger infrastructure — connection, migrations, guards, kill switch.

Mirrors ``case_journal.py``'s discipline (env-overridable location, append-only,
best-effort, stdlib only) but stores a different grain: the journal records one
milestone line per project; this records per-coil / per-field observations for
the ML corpus. They run side by side — the journal is a documented cross-repo
contract and is NOT absorbed here.

Hard rules:
- A capture failure must NEVER break a CoilForge request.
- ...but it must never be SILENT either. Silent best-effort writes are exactly how
  four journal milestones were lost. Every failure lands in ``capture_error``; a
  failure that prevents even that (bad config) is remembered in ``last_error()``
  and printed once to stderr.

What the DB does and does not hold (stated exactly, because "hashes only" would be
a comfortable overclaim):
- NEVER raw customer bytes or extracted document text. PDFs and SVGs are reduced to
  a hash + length; ``source_filename`` is hashed because filenames carry customer
  names.
- DOES hold, in cleartext: ``run.project_number`` / ``run.project_name`` /
  ``coil.tag``, plus normalized engineering values and the ``source_evidence`` the
  API already returns to the browser. Hashing the project identifier was considered
  and REJECTED — John is the ledger's only reader and project is the dimension he
  filters on; pseudonymizing it would make the corpus useless to its one user.
  The journal already records the same identifiers.
- The consequence to keep in view: the journal is one file per day, this is ALL
  history in one file. Losing it is categorically worse — hence the outside-repo
  default, the .git-walk guard, and the .gitignore patterns.
"""

from __future__ import annotations

import hashlib
import os
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from coilforge.capture.schema import CAPTURE_SCHEMA_VERSION, MIGRATIONS

ENV_CAPTURE_DB = "COILFORGE_CAPTURE_DB"
ENV_CAPTURE_ENABLED = "COILFORGE_CAPTURE"

_REPO_ROOT = Path(__file__).resolve().parents[3]

_last_error: str | None = None
_warned = False


class CaptureConfigError(RuntimeError):
    """The ledger is misconfigured — e.g. the DB path resolves inside a git repo."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def capture_enabled() -> bool:
    """Kill switch: ``COILFORGE_CAPTURE=0`` disables the ledger without reverting
    the branch. Read at request time so it can be toggled in a running process.
    Default ON.

    Mirrors ``web_app._manual_fill_enabled`` EXACTLY, including its quirk: a
    set-but-empty value reads as OFF, while *unset* reads as ON. (Note this is the
    opposite convention from ``case_journal.journal_dir``'s ``.strip() or
    DEFAULT`` — the two idioms are deliberately different; do not "harmonize" them.)
    """
    return os.environ.get(ENV_CAPTURE_ENABLED, "1").strip().lower() not in (
        "0", "false", "no", "off", "",
    )


def _default_db_path() -> Path:
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("XDG_DATA_HOME")
    if not base:
        base = str(Path.home() / ".local" / "share")
    return Path(base) / "CoilForge" / "capture" / "coilforge.sqlite3"


def capture_db_path() -> Path:
    """Ledger location. ``COILFORGE_CAPTURE_DB`` overrides; blank/whitespace falls
    back to the default (the ``case_journal.journal_dir`` idiom)."""
    raw = os.environ.get(ENV_CAPTURE_DB, "").strip()
    return Path(raw) if raw else _default_db_path()


def assert_outside_repo(path: Path) -> None:
    """Refuse a DB path inside ANY git working tree.

    The ledger accumulates every project it has ever seen into one file; the
    repo's .gitignore blocks raw customer data by pattern, and this is the
    mechanical backstop for the same posture.

    Walks for ``.git`` rather than comparing against ``phase2a.app.REPO_ROOT``:
    inside a worktree (``.claude/worktrees/phase2``) that constant resolves to the
    WORKTREE root and would happily accept a path in the main checkout. A worktree
    marks itself with a ``.git`` FILE, not a directory — ``.exists()`` covers both.
    """
    resolved = path.resolve()
    for parent in (resolved, *resolved.parents):
        if (parent / ".git").exists():
            raise CaptureConfigError(
                f"refusing capture DB inside a git repo: {resolved} (found {parent / '.git'}). "
                f"Set {ENV_CAPTURE_DB} to a path outside the checkout."
            )


def note_error(message: str) -> None:
    """Remember a capture failure that could not be written to ``capture_error``.

    Printed once per process: a ledger that records nothing for six months and
    says nothing is the single highest-severity failure mode of this design.
    """
    global _last_error, _warned
    _last_error = message
    if not _warned:
        _warned = True
        print(f"[coilforge.capture] disabled: {message}", file=sys.stderr)


def last_error() -> str | None:
    """The most recent capture failure, for the /api/capture/health route (1d)."""
    return _last_error


def connect() -> sqlite3.Connection:
    """Open (and migrate) the ledger. Raises CaptureConfigError / sqlite3.Error —
    callers are responsible for never letting that reach the request."""
    path = capture_db_path()
    assert_outside_repo(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=5.0)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    # Worktree servers (phase2 / phase5) write to the same file; without a busy
    # timeout a concurrent flush fails instantly with SQLITE_BUSY.
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=OFF")
    _migrate(conn)
    return conn


def _migrate(conn: sqlite3.Connection) -> None:
    """Forward-only. ``PRAGMA user_version`` is the version of record — it survives
    an empty DB, so there is no bootstrap chicken-and-egg with the ledger table."""
    current = int(conn.execute("PRAGMA user_version").fetchone()[0])
    if current >= len(MIGRATIONS):
        return
    for index in range(current, len(MIGRATIONS)):
        description, statements = MIGRATIONS[index]
        version = index + 1
        digest = hashlib.sha256("\n".join(statements).encode("utf-8")).hexdigest()
        with conn:
            for statement in statements:
                conn.execute(statement)
            conn.execute(
                "INSERT INTO migration (version, applied_ts, description, sql_sha256)"
                " VALUES (?, ?, ?, ?)",
                (version, utc_now(), description, digest),
            )
            # PRAGMA cannot be parameterized; version is an int from range().
            conn.execute(f"PRAGMA user_version = {version}")


def record_error(
    phase: str,
    error: str,
    *,
    run_id: str | None = None,
    context_json: str | None = None,
) -> None:
    """Log a capture failure into the ledger. Never raises: if even this fails the
    message falls back to ``note_error`` so it is not lost entirely."""
    try:
        conn = connect()
        try:
            with conn:
                conn.execute(
                    "INSERT INTO capture_error (ts_utc, run_id, phase, error, context_json)"
                    " VALUES (?, ?, ?, ?, ?)",
                    (utc_now(), run_id, phase, error, context_json),
                )
        finally:
            conn.close()
    except Exception as exc:  # noqa: BLE001 — the error log must not raise
        note_error(f"{phase}: {error} (and capture_error write failed: {exc})")


# --- Computation identity ---------------------------------------------------
# Computed ONCE per process and cached. Deliberate: `git describe` at request time
# lies when src/ was edited without restarting the no-reload server (a standing
# trap) -- git reports the new commit while the running process holds the old code.
# The process's identity is fixed at start; so is this label.

_code_version: str | None = None
_rules_hash: str | None = None
_catalog_version: str | None = None


def code_version() -> str:
    global _code_version
    if _code_version is None:
        try:
            _code_version = subprocess.run(
                ["git", "describe", "--always", "--dirty"],
                cwd=str(_REPO_ROOT),
                capture_output=True,
                text=True,
                timeout=5,
                check=True,
            ).stdout.strip() or "unknown"
        except Exception:  # noqa: BLE001 — git absent / not a checkout
            _code_version = "unknown"
    return _code_version


def _file_sha256(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except Exception:  # noqa: BLE001
        return None


def rules_hash() -> str | None:
    """sha256 of the rule table. Without it a months-old rule_firing (1c) would be
    uninterpretable after a YAML edit."""
    global _rules_hash
    if _rules_hash is None:
        _rules_hash = _file_sha256(
            _REPO_ROOT / "src" / "coilforge" / "rules" / "coil_header_rules.yaml"
        ) or ""
    return _rules_hash or None


def catalog_version() -> str | None:
    """sha256 of the template catalog source.

    Limitation, stated rather than hidden: this tracks catalog.py only, so a
    re-seeded slot_map.json / template.svg does NOT change it. Good enough to
    attribute a bucket-routing change; not a content hash of the artwork.
    """
    global _catalog_version
    if _catalog_version is None:
        _catalog_version = _file_sha256(
            _REPO_ROOT / "src" / "coilforge" / "template_population" / "catalog.py"
        ) or ""
    return _catalog_version or None


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha1_bytes(data: bytes) -> str:
    """sha1 to match ``_workflow_cache_key``'s pdf_sha1 — the same PDF must produce
    the same input_hash the workflow cache would key on."""
    return hashlib.sha1(data).hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()


def reset_caches_for_tests() -> None:
    """Drop the memoized process identity + the one-shot warning latch."""
    global _code_version, _rules_hash, _catalog_version, _last_error, _warned
    _code_version = _rules_hash = _catalog_version = None
    _last_error = None
    _warned = False
