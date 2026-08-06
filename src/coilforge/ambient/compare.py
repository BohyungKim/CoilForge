"""Per-field tolerance policy + verdict stamping for the Ambient comparison.

Reuses the single project comparator ``checklist.compare._match`` (the same function
``ccsi.compare`` imports) — extended with a keyword-only relative tolerance so
performance quantities (capacity in MBH, airflow, pressure drops) are compared with a
percentage band instead of the dimensional 0.01" default.

``_FIELD_TOL`` is an **engineering-judgment table** shipped as review-only defaults
(John to confirm the bands). It is NOT an accept/reject authority: a "match" here means
"agrees within the review band", never "approved".
"""
from __future__ import annotations

from coilforge.checklist.compare import _match
from coilforge.ambient.model import Verdict

# tol_key -> {"tol": abs_inches_or_units, "rel_tol": fraction}. Review-only defaults.
_FIELD_TOL: dict[str, dict[str, float]] = {
    "capacity": {"rel_tol": 0.02},        # MBH — ±2%
    "coil_volume": {"rel_tol": 0.02},     # in^3 — ±2%
    "airflow": {"rel_tol": 0.02},         # CFM — ±2%
    "face_velocity": {"rel_tol": 0.02},   # FPM — ±2%
    "air_pd": {"rel_tol": 0.05},          # inWG — ±5%
    "refrigerant_pd": {"rel_tol": 0.05},  # psi — ±5%
    "temp": {"tol": 0.5},                 # °F — ±0.5 absolute
    "dim": {"tol": 0.01},                 # in — fin height/length, dimensional
    "count": {"tol": 0.0},                # rows / FPI / feeds — exact
    "string": {"tol": 0.0},               # material / surface / connection — exact text
}

# Human-readable provenance shown per row (the "tolerance" column).
_TOL_LABEL: dict[str, str] = {
    "capacity": "rel 2%",
    "coil_volume": "rel 2%",
    "airflow": "rel 2%",
    "face_velocity": "rel 2%",
    "air_pd": "rel 5%",
    "refrigerant_pd": "rel 5%",
    "temp": "±0.5°F",
    "dim": "±0.01 in",
    "count": "exact",
    "string": "exact",
}


def tolerance_label(tol_key: str) -> str:
    return _TOL_LABEL.get(tol_key, "±0.01")


def field_verdict(baseline: object, ambient: object, tol_key: str) -> Verdict:
    """Verdict for one field via the shared comparator + this field's tolerance band."""
    spec = _FIELD_TOL.get(tol_key, {})
    return _match(  # type: ignore[return-value]
        baseline,
        ambient,
        tol=spec.get("tol", 0.01),
        rel_tol=spec.get("rel_tol"),
    )
