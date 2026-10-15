"""Move a stranded capture ledger to the current (non-redirected) location.

Why this exists: until 2026-08-11 the Windows default sat under ``%LOCALAPPDATA%``,
which the Microsoft Store Python — an MSIX package — silently redirects into its own
``LocalCache``. The corpus therefore accumulated inside a container that Windows
empties on an app Reset, and a non-packaged interpreter resolved the same code to a
different file. ``capture.db._default_db_path`` now pins a plain profile directory;
this script carries the existing rows across.

Safety posture, in order of how much it matters:

- The SOURCE is opened read-only and is NEVER deleted. Removing it is John's call,
  after he has seen the new ledger accumulate.
- Copying is ``VACUUM INTO``, not a file copy: it folds the -wal sidecar into one
  consistent file, so the "copied the .sqlite3 and lost the WAL" accident cannot
  happen. It also preserves ``PRAGMA user_version`` (the migration state).
- Every table's row count is compared before/after. A mismatch DELETES the new file
  and exits non-zero — a half-migrated ledger is worse than none, because the server
  would start filling it while the real corpus sits elsewhere.
- Refuses to overwrite an existing destination.

Stop the server first: a running uvicorn holds the source open and may write mid-copy.

Usage:
    python scripts/migrate_capture_ledger.py                  # dry run (default)
    python scripts/migrate_capture_ledger.py --apply
    python scripts/migrate_capture_ledger.py --source <path> --apply
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from coilforge.capture import db  # noqa: E402


def _connect_ro(path: Path) -> sqlite3.Connection:
    """Read-only handle. The URI form is what makes it genuinely read-only —
    a plain connect() would create the file if it were missing."""
    return sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)


def _snapshot(conn: sqlite3.Connection) -> tuple[int, dict[str, int]]:
    """(user_version, {table: row_count}) for every real table.

    Read from sqlite_master rather than a hardcoded list: the point of the check is
    to catch a table this script did not anticipate going missing, and a hardcoded
    list can only verify what it already knows about.
    """
    version = int(conn.execute("PRAGMA user_version").fetchone()[0])
    tables = [
        name
        for (name,) in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
            " AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )
    ]
    counts = {
        # Table names come from sqlite_master, not user input -- not parameterizable.
        name: int(conn.execute(f"SELECT COUNT(*) FROM '{name}'").fetchone()[0])
        for name in tables
    }
    return version, counts


def _resolve_source(explicit: str | None) -> Path | None:
    if explicit:
        return Path(explicit)
    found = db.legacy_db_paths()
    if not found:
        return None
    if len(found) > 1:
        print("several stranded ledgers found — re-run with --source <path>:")
        for path in found:
            print(f"    {path}  ({path.stat().st_size:,} bytes)")
        raise SystemExit(2)
    return found[0]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Migrate a stranded capture ledger to the current location."
    )
    parser.add_argument("--source", help="ledger to migrate (default: auto-detect)")
    parser.add_argument(
        "--apply", action="store_true", help="actually migrate (default is a dry run)"
    )
    args = parser.parse_args()

    dest = db.capture_db_path()
    source = _resolve_source(args.source)
    if source is None:
        print(f"nothing to migrate — no stranded ledger found.\ncurrent ledger: {dest}")
        return 0
    if not source.is_file():
        print(f"source is not a file: {source}")
        return 1
    if source.resolve() == dest.resolve():
        print(f"source and destination are the same file: {dest}")
        return 1

    db.assert_outside_repo(dest)

    conn = _connect_ro(source)
    try:
        version, counts = _snapshot(conn)
    finally:
        conn.close()

    print(f"source : {source}  ({source.stat().st_size:,} bytes)")
    print(f"dest   : {dest}")
    print(f"user_version: {version}")
    for name, count in counts.items():
        print(f"    {name:<26} {count:>8,}")

    if not args.apply:
        print("\ndry run — nothing written. Re-run with --apply (stop the server first).")
        return 0

    if dest.exists():
        print(f"\nrefusing to overwrite an existing ledger: {dest}")
        return 1
    dest.parent.mkdir(parents=True, exist_ok=True)

    conn = _connect_ro(source)
    try:
        # Read-only w.r.t. the source by SQLite's own definition of VACUUM INTO.
        conn.execute("VACUUM INTO ?", (str(dest),))
    finally:
        conn.close()

    conn = _connect_ro(dest)
    try:
        new_version, new_counts = _snapshot(conn)
        ok = conn.execute("PRAGMA integrity_check").fetchone()[0]
    finally:
        conn.close()

    problems: list[str] = []
    if ok != "ok":
        problems.append(f"integrity_check returned {ok!r}")
    if new_version != version:
        problems.append(f"user_version {version} -> {new_version}")
    for name, count in counts.items():
        if new_counts.get(name) != count:
            problems.append(f"{name}: {count} -> {new_counts.get(name)}")
    for name in set(new_counts) - set(counts):
        problems.append(f"unexpected extra table {name}")

    if problems:
        # Leave nothing half-migrated behind: the server would happily fill it.
        dest.unlink(missing_ok=True)
        print("\nMIGRATION FAILED — destination removed, source untouched:")
        for problem in problems:
            print(f"    {problem}")
        return 1

    print(f"\nmigrated: {sum(counts.values()):,} rows across {len(counts)} tables, "
          f"integrity ok, user_version {new_version}")
    print(f"new ledger: {dest}  ({dest.stat().st_size:,} bytes)")
    print(f"\nThe source was NOT deleted. Leave it until the new ledger has grown across a\n"
          f"few real runs, then remove it yourself:\n    {source}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
