"""Build the download-free submittal PDF index (metadata only; no PDF is opened).

Walks the OneDrive PO tree (``deliverable.finalize.DEFAULT_PO_BASE``) plus the extra
roots and writes ``<data>/index.json`` outside the repo
(``COILFORGE_SUBMITTAL_INDEX_DIR`` or ``~/CoilForgeData/submittal_index``).

    python scripts/build_submittal_index.py
    python scripts/build_submittal_index.py --extra-root "C:\\path\\to\\more\\pdfs"

Extra roots are absolute on purpose: a worktree has no ``submittals/`` (gitignored),
so a relative default would silently index nothing.
"""
from __future__ import annotations

import argparse
import collections
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from coilforge.corpus.fs import resolve_data_dir  # noqa: E402
from coilforge.corpus.submittal_index import scan, write_index  # noqa: E402
from coilforge.deliverable.finalize import DEFAULT_PO_BASE  # noqa: E402

DEFAULT_EXTRA_ROOTS = (
    r"C:\Users\JohnKim\Desktop\Bins\Projects\CoilForge\submittals",
    r"C:\Users\JohnKim\Desktop\Bins\Projects\PO_Release_Case\intake\processed",
)


def main(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--po-base", default=DEFAULT_PO_BASE)
    parser.add_argument("--extra-root", action="append", default=None,
                        help="absolute path; repeatable (default: repo submittals/ + PO_Release_Case intake)")
    parser.add_argument("--index-dir", default=None)
    args = parser.parse_args(argv)

    extra_roots = []
    for root in args.extra_root if args.extra_root is not None else DEFAULT_EXTRA_ROOTS:
        if Path(root).is_dir():
            extra_roots.append(root)
        else:
            print(f"skip missing extra root: {root}")

    index = scan(args.po_base, extra_roots)
    data_dir = resolve_data_dir(args.index_dir)
    target = write_index(index, data_dir)

    entries = index.entries
    submittal_named = [e for e in entries if e.name_has_submittal]
    reasons = collections.Counter(reason for e in entries for reason in e.reasons)
    print(f"index written: {target}")
    print(f"roots: {len(index.roots)}  scan_errors: {len(index.scan_errors)}")
    print(f"pdfs: {len(entries)}  submittal-named: {len(submittal_named)}  "
          f"oxygen8-named: {sum(e.oxygen8_named for e in entries)}")
    print(f"cloud-only (all / submittal-named): {sum(e.cloud_only_at_scan for e in entries)} / "
          f"{sum(e.cloud_only_at_scan for e in submittal_named)}  "
          f"cloud-only GB (submittal-named): "
          f"{sum(e.size for e in submittal_named if e.cloud_only_at_scan) / 1e9:.1f}")
    print(f"long paths (all / submittal-named): {sum(e.long_path for e in entries)} / "
          f"{sum(e.long_path for e in submittal_named)}")
    print(f"projects with a number: {len({e.project_number for e in entries if e.project_number})}")
    print("reasons: " + ", ".join(f"{k}={v}" for k, v in sorted(reasons.items())))
    for error in index.scan_errors[:10]:
        print(f"  scan error: {error.path}: {error.error}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
