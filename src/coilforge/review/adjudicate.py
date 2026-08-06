"""Record a human ruling on a divergence: ledger row + staging-registry entry.

Two writes, deliberately different in kind:

* **The ledger** (`divergence_adjudication`, append-only) gets EVERY ruling, including
  ``unresolved``. It is the audit trail — "when did we decide this, and what did we know
  then" — and a ruling that decided nothing is still a fact about the review.
* **The staging registry** (`outputs/divergence_staging.yaml`) gets only rulings that can
  actually annotate a row. ``unresolved`` is excluded on purpose: "I looked and could not
  decide" must never suppress anything.

The route writes ONLY to the gitignored staging file, never to
`rules/known_divergences.yaml`. A concurrent session auto-commits this working tree, so a
browser action that touched a tracked path could smuggle an un-reviewed ruling into a
commit. Promotion is a separate, explicit step John runs (`scripts/promote_divergences.py`)
and his commit is the approval.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from coilforge.capture import db
from coilforge.review.divergence import (
    ANY_SIZE,
    REGISTERABLE,
    VERDICTS,
    _STAGING_PATH,
    divergence_key,
    load_registry,
)

_ID_RE = re.compile(r"^KD-(\d+)$")


class AdjudicationError(ValueError):
    """Bad ruling — surfaced as a 400, never a 500."""


def _next_id(*, promoted_path: Path | None = None, staging_path: Path | None = None) -> str:
    """Next free ``KD-###`` across BOTH files. Scanning both matters: numbering only the
    staging file would re-issue an id already promoted, and two different rulings sharing
    an id makes the ledger's ``registry_id`` ambiguous."""
    registry = load_registry(promoted_path=promoted_path, staging_path=staging_path)
    highest = 0
    for entry in registry.entries:
        match = _ID_RE.match(entry.id)
        if match:
            highest = max(highest, int(match.group(1)))
    return f"KD-{highest + 1:03d}"


def _append_staging(entry: dict[str, Any], *, staging_path: Path) -> None:
    staging_path.parent.mkdir(parents=True, exist_ok=True)
    doc: dict[str, Any] = {"version": 1, "divergences": []}
    if staging_path.exists():
        loaded = yaml.safe_load(staging_path.read_text(encoding="utf-8")) or {}
        if isinstance(loaded, dict):
            doc["divergences"] = list(loaded.get("divergences") or [])
    doc["divergences"].append(entry)
    header = (
        "# WORKING FILE — written by POST /api/divergence/adjudicate. GITIGNORED.\n"
        "# Not the registry of record: promote with scripts/promote_divergences.py, then\n"
        "# commit. Entries here annotate review rows immediately but are badged '미승격'.\n"
        "# Kept inside the checkout (unlike the capture DB, which assert_outside_repo\n"
        "# pushes out) because John has to READ and promote it — it is small and carries\n"
        "# no customer identifiers.\n"
    )
    staging_path.write_text(
        header + yaml.safe_dump(doc, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )


def _record_ledger(row: dict[str, Any]) -> str | None:
    """Append the ruling to the capture ledger. Never raises into the request — a ledger
    outage must not block the engineer from recording a decision, but it IS reported so a
    silently-unrecorded ruling cannot masquerade as a recorded one."""
    if not db.capture_enabled():
        return "capture is disabled — the ruling was not written to the ledger"
    try:
        conn = db.connect()
        try:
            with conn:
                conn.execute(
                    "INSERT INTO divergence_adjudication (ts_utc, divergence_key,"
                    " coil_category, product_family, terra_variant, unit_size_scope, slot,"
                    " verdict, reason, evidence_json, adjudicated_by, delta_min, delta_max,"
                    " registry_id, run_id, coil_tag)"
                    " VALUES (" + ",".join("?" * 16) + ")",
                    (
                        row["ts_utc"], row["divergence_key"], row["coil_category"],
                        row["product_family"], row["terra_variant"], row["unit_size_scope"],
                        row["slot"], row["verdict"], row["reason"], row["evidence_json"],
                        row["adjudicated_by"], row["delta_min"], row["delta_max"],
                        row["registry_id"], row["run_id"], row["coil_tag"],
                    ),
                )
        finally:
            conn.close()
    except Exception as exc:  # noqa: BLE001 -- honour the never-raise contract
        db.note_error(f"divergence adjudication not recorded: {exc}")
        return f"the ruling was not written to the ledger: {exc}"
    return None


def record_adjudication(
    payload: dict[str, Any],
    *,
    staging_path: Path | None = None,
    promoted_path: Path | None = None,
) -> dict[str, Any]:
    """Validate and record one ruling. Raises ``AdjudicationError`` for a 400."""
    verdict = str(payload.get("verdict") or "").strip()
    if verdict not in VERDICTS:
        raise AdjudicationError(f"verdict must be one of {VERDICTS}")

    # An empty reason is rejected rather than defaulted. The registry's entire claim to
    # not being an invention is that every entry carries a human's stated why; a blank
    # reason would make it a machine-accumulated suppression list.
    reason = str(payload.get("reason") or "").strip()
    if not reason:
        raise AdjudicationError("a ruling requires a non-empty reason")

    slot = str(payload.get("slot") or "").strip()
    if not slot:
        raise AdjudicationError("a ruling requires the slot it applies to")
    category = str(payload.get("coil_category") or "").strip()
    if not category:
        raise AdjudicationError("a ruling requires the coil category")

    scope = payload.get("unit_size_scope")
    scope = ANY_SIZE if scope in (None, "", ANY_SIZE) else str(scope).strip()

    band = payload.get("delta_band")
    delta_min = delta_max = None
    if band is not None:
        try:
            if isinstance(band, dict):
                delta_min, delta_max = float(band["min"]), float(band["max"])
            else:
                delta_min, delta_max = float(band[0]), float(band[1])
        except Exception as exc:  # noqa: BLE001
            raise AdjudicationError(f"delta_band must be {{min, max}}: {exc}") from exc
        if delta_min > delta_max:
            raise AdjudicationError("delta_band min exceeds max")

    family = str(payload.get("product_family") or "").strip()
    variant = str(payload.get("terra_variant") or "").strip()
    key = divergence_key(category, family, variant, scope, slot)

    staging = staging_path or _STAGING_PATH
    registry_id = None
    if verdict in REGISTERABLE:
        registry_id = _next_id(promoted_path=promoted_path, staging_path=staging)
        entry: dict[str, Any] = {
            "id": registry_id,
            "coil_category": category,
            "product_family": family or None,
            "terra_variant": variant or None,
            "unit_size_scope": scope,
            "slot": slot,
            "verdict": verdict,
            "reason": reason,
            "status": "proposed",
            "adjudicated_by": str(payload.get("adjudicated_by") or "John"),
            "adjudicated_utc": db.utc_now(),
        }
        if payload.get("evidence_refs"):
            entry["evidence_refs"] = list(payload["evidence_refs"])
        if band is not None:
            entry["delta_band"] = {"min": delta_min, "max": delta_max}
        if payload.get("expires_utc"):
            entry["expires_utc"] = str(payload["expires_utc"])
        _append_staging(entry, staging_path=staging)

    ledger_warning = _record_ledger(
        {
            "ts_utc": db.utc_now(),
            "divergence_key": key,
            "coil_category": category,
            "product_family": family or None,
            "terra_variant": variant or None,
            "unit_size_scope": scope,
            "slot": slot,
            "verdict": verdict,
            "reason": reason,
            "evidence_json": (
                yaml.safe_dump(list(payload["evidence_refs"]))
                if payload.get("evidence_refs") else None
            ),
            "adjudicated_by": str(payload.get("adjudicated_by") or "John"),
            "delta_min": delta_min,
            "delta_max": delta_max,
            "registry_id": registry_id,
            "run_id": payload.get("run_id"),
            "coil_tag": payload.get("coil_tag"),
        }
    )

    return {
        "recorded": True,
        "divergence_key": key,
        "registry_id": registry_id,
        # `unresolved` intentionally produces no registry entry — say so, so the caller
        # does not read a missing id as a failure.
        "registered": registry_id is not None,
        "promoted": False,
        "staging_path": str(staging),
        "warnings": [w for w in (ledger_warning,) if w],
        "export_allowed": False,
        "production_drawing_approval_claimed": False,
    }
