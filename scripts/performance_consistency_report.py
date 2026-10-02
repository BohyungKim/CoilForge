"""Measure the performance self-consistency checks on the ordered-coil corpus (read-only).

    python scripts/performance_consistency_report.py --crosscheck C:\\...\\crosscheck.json
    python scripts/performance_consistency_report.py --crosscheck C:\\...\\crosscheck.json ^
        --sources-cache C:\\...\\ccsi_report_crosscheck\\cache

Both inputs are absolute on purpose: they live in another working tree's gitignored
``outputs/``, and a relative default would silently read nothing (or the wrong tree).
The report names project numbers and coil tags, so it is written OUTSIDE the repo
(``~/CoilForgeData/performance_consistency`` unless ``--out-dir`` says otherwise).

Exit 2 = an input is missing, truncated or not the expected structure; nothing is written.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from coilforge.capture.db import CaptureConfigError, assert_outside_repo  # noqa: E402
from coilforge.corpus.fs import atomic_write_text  # noqa: E402
from coilforge.corpus.performance_consistency_report import (  # noqa: E402
    ReportInputError,
    build_report,
    load_cache_coils,
    read_json,
    render_markdown,
    validate_crosscheck_document,
)

DEFAULT_OUT_DIR = Path.home() / "CoilForgeData" / "performance_consistency"


def main(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--crosscheck", required=True, help="absolute path to the runner's crosscheck.json")
    parser.add_argument("--sources-cache", default=None, help="absolute path to the runner's cache/ folder")
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    args = parser.parse_args(argv)

    crosscheck = Path(args.crosscheck)
    cache_dir = Path(args.sources_cache) if args.sources_cache else None
    out_dir = Path(args.out_dir)
    try:
        for label, path in (("--crosscheck", crosscheck), ("--sources-cache", cache_dir)):
            if path is not None and not path.is_absolute():
                raise ReportInputError(f"{label} must be an absolute path: {path}")
        if cache_dir is not None and not cache_dir.is_dir():
            raise ReportInputError(f"--sources-cache is not a directory: {cache_dir}")
        try:
            assert_outside_repo(out_dir)
        except CaptureConfigError as exc:  # its message speaks of the capture DB, not this report
            raise ReportInputError(f"--out-dir is inside a git working tree: {out_dir}") from exc
        doc = read_json(crosscheck)
        problems = validate_crosscheck_document(doc)
        if problems:
            raise ReportInputError("crosscheck.json is not the expected structure:\n  " + "\n  ".join(problems))
        cache_coils = None if cache_dir is None else load_cache_coils(cache_dir, str(doc.get("code_version")))
    except ReportInputError as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2

    report = build_report(doc, cache_coils)
    atomic_write_text(out_dir / "report.json", json.dumps(report, indent=2, ensure_ascii=False))
    atomic_write_text(out_dir / "report.md", render_markdown(report))

    defaults = report["defaults"]
    stamp = f"F {defaults['sensible_factor']}, tol ±{defaults['k_tolerance']}"
    heating = report["heating"]
    print(f"report written: {out_dir}")
    print(f"heating ({stamp}): {heating['evaluable']} evaluable of {heating['coils']} — {heating['verdicts']}")
    print(f"fluid band self-check (must be 0): {report['fluid']['band_self_check_outside']} "
          f"of {report['fluid']['band_self_check_coils']} checked")
    print(f"face velocity: {report['face_velocity']}")
    push = report.get("push_time_sources")
    if push:
        dx = push["dx_sensible"]
        print(f"DX sensible ({stamp}): {dx['evaluable']} evaluable of {dx['coils']} — {dx['verdicts']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
