"""Compare a human's Direct Coil web entry against CoilForge's canonical record.

The *alert* half of the Phase 2 "read-and-alert" verifier (workflow step 6).
CoilForge does not edit the website; it reads what John entered (``page_reader``)
and flags where it disagrees with the canonical data CoilForge already holds for
that coil — an alerting system, not an actor.

Design notes (see the plan for the why):

- **Asymmetric on purpose.** ``compare_submittal_and_ez`` diffs two fully-formed
  canonical records; the web entry is bare typed values with no evidence, which the
  ``FieldValue`` contract refuses to wrap. So this is a one-sided comparator:
  CoilForge ``CanonicalCoilRecord`` (carrying confidence/status) vs a plain
  ``{normalized_key: value}`` dict, aligned by ``CANONICAL_DIRECT_COIL_FIELD_MAP``.
- **Severity is the confidence gate, reused.** A mismatch against a CoilForge
  ``confirmed`` value is loud (likely a human typo); against an ``inferred`` value
  it is soft (CoilForge itself may be wrong); a blocked/missing CoilForge value is
  un-verifiable, not a conflict. No new severity model is invented.
- **No false reassurance.** Parse coverage rides through so a near-empty read can
  never look like a clean pass.

Pure function — no I/O. The frozen ``_conn_float`` / ``_slot_inches`` helpers are
*not* imported (they live in do-not-touch modules); this module keeps its own
``_normalize_for_compare`` instead.
"""

from __future__ import annotations

import re
from typing import Any

from coilforge.contracts.canonical import CanonicalCoilRecord
from coilforge.contracts.field_value import FieldValue
from coilforge.direct_coil.paste_ready_fields import DIRECT_COIL_PASTE_FIELD_ORDER
from coilforge.validation.canonical_rules import (
    CANONICAL_DIRECT_COIL_FIELD_MAP,
    _get_record_field_value,
)

# Canonical field_key -> the paste-surface spec that carries its Direct Coil label
# and the ``normalized_key`` the page reader stores its value under. First spec wins.
_PASTE_BY_CANONICAL_KEY = {}
for _spec in DIRECT_COIL_PASTE_FIELD_ORDER:
    if _spec.draft_field_key is not None:
        _PASTE_BY_CANONICAL_KEY.setdefault(_spec.draft_field_key, _spec)

_NUMERIC_TOLERANCE = 0.02  # inches; same idiom as pdf_to_template_drawing._validation
_REVIEW_REQUIRED = "REVIEW REQUIRED"
_SEVERITY_RANK = {"high": 0, "medium": 1, "info": 2}


def _leading_number(text: str) -> float | None:
    """Numeric value of a string that *starts* with a number or fraction.

    ``"5/8" -> 0.625``, ``"1 1/2" -> 1.5``, ``'0.625" OD' -> 0.625``, ``"47 in" -> 47``.
    Returns ``None`` for word-leading strings ('Copper', 'R-410A', 'Left') so material
    and refrigerant fields stay string comparisons — only digit-leading fields coerce."""
    s = text.strip().lstrip('"').strip()
    if not s or not (s[0].isdigit() or s[0] in "-."):
        return None
    mixed = re.match(r"^(\d+)\s+(\d+)/(\d+)", s)
    if mixed:
        return int(mixed[1]) + int(mixed[2]) / int(mixed[3])
    frac = re.match(r"^(\d+)/(\d+)", s)
    if frac:
        return int(frac[1]) / int(frac[2])
    num = re.match(r"^-?\d+(?:\.\d+)?", s)
    return float(num.group(0)) if num else None


def _normalize_for_compare(value: Any) -> float | str | None:
    """Coerce a value for comparison: number (with fraction/unit handling) or a
    case-folded string. ``None`` / blank / 'REVIEW REQUIRED' -> ``None`` (not comparable)."""
    if value is None:
        return None
    if isinstance(value, bool):
        return str(value).casefold()
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text or text.upper() == _REVIEW_REQUIRED:
        return None
    number = _leading_number(text)
    if number is not None:
        return number
    return text.casefold()


def _values_match(coilforge_raw: Any, entered_raw: Any) -> bool | None:
    """``True``/``False`` match, or ``None`` when either side is not comparable."""
    a = _normalize_for_compare(coilforge_raw)
    b = _normalize_for_compare(entered_raw)
    if a is None or b is None:
        return None
    if isinstance(a, float) and isinstance(b, float):
        return abs(a - b) < _NUMERIC_TOLERANCE
    if isinstance(a, float) != isinstance(b, float):
        # one numeric, one word — fall back to a literal string comparison
        return str(coilforge_raw).strip().casefold() == str(entered_raw).strip().casefold()
    return a == b


def _coilforge_present(field_value: FieldValue | None) -> bool:
    """Does CoilForge hold a trustworthy value to compare against?"""
    if field_value is None:
        return False
    if field_value.value in (None, ""):
        return False
    if field_value.status == "blocked":
        return False
    if field_value.confidence == "missing":
        return False
    return True


def verify_entered_values(
    entered: dict[str, Any],
    record: CanonicalCoilRecord,
    *,
    coil_tag: str | None = None,
) -> dict[str, Any]:
    """Diff entered Direct Coil values against the canonical record.

    ``entered`` is keyed by paste-surface ``normalized_key`` (the page reader's
    output). Returns only the *actionable* rows (mismatches + un-verifiable), the
    match/mismatch counts, and the parse-coverage signal that guards against a
    near-empty read masquerading as a clean pass. Review aid only."""
    discrepancies: list[dict[str, Any]] = []
    match_count = 0
    mismatch_count = 0
    unverifiable_count = 0
    fields_expected = 0
    fields_read = 0

    for field_key, canonical_path in CANONICAL_DIRECT_COIL_FIELD_MAP.items():
        spec = _PASTE_BY_CANONICAL_KEY.get(field_key)
        if spec is None:
            continue  # field has no Direct Coil entry surface — not page-readable
        fields_expected += 1

        field_value = _get_record_field_value(record, canonical_path)
        entered_raw = entered.get(spec.normalized_key)
        entered_present = entered_raw not in (None, "")
        if entered_present:
            fields_read += 1

        coilforge_present = _coilforge_present(field_value)
        coilforge_value = field_value.value if field_value is not None else None
        confidence = field_value.confidence if field_value is not None else None
        status = field_value.status if field_value is not None else None

        if not entered_present:
            continue  # nothing typed for this field yet — not a conflict, skip the row

        if not coilforge_present:
            # Something was entered, but CoilForge has nothing trustworthy to check it
            # against (blocked / missing / no value) — flag it, never claim "verified".
            unverifiable_count += 1
            discrepancies.append(
                _row(
                    spec,
                    field_key,
                    coilforge_value,
                    confidence,
                    status,
                    entered_raw,
                    match=False,
                    severity="info",
                    note=(
                        "CoilForge has no confirmed value for this field — "
                        "cannot verify; review manually."
                    ),
                )
            )
            continue

        result = _values_match(coilforge_value, entered_raw)
        if result is None:
            unverifiable_count += 1
            discrepancies.append(
                _row(
                    spec, field_key, coilforge_value, confidence, status, entered_raw,
                    match=False, severity="info",
                    note="Value could not be compared (non-numeric / review-required).",
                )
            )
        elif result:
            match_count += 1
        else:
            mismatch_count += 1
            severity = "high" if confidence == "confirmed" else "medium"
            note = (
                "Entered value disagrees with CoilForge's confirmed value — likely a "
                "transcription error; review."
                if severity == "high"
                else "Entered value disagrees with a CoilForge inferred value — CoilForge "
                "may be wrong; review."
            )
            discrepancies.append(
                _row(
                    spec, field_key, coilforge_value, confidence, status, entered_raw,
                    match=False, severity=severity, note=note,
                )
            )

    discrepancies.sort(key=lambda row: (_SEVERITY_RANK[row["severity"]], row["field_key"]))
    low_coverage_warning = fields_expected > 0 and fields_read < 0.25 * fields_expected

    return {
        "coil_tag": coil_tag,
        "discrepancies": discrepancies,
        "match_count": match_count,
        "mismatch_count": mismatch_count,
        "unverifiable_count": unverifiable_count,
        "fields_read": fields_read,
        "fields_expected": fields_expected,
        "low_coverage_warning": low_coverage_warning,
        # Review-aid safety contract — never relaxed by this layer.
        "export_allowed": False,
        "raw_private_data_returned": False,
        "production_drawing_approval_claimed": False,
    }


def verify_entered_against_candidate(
    entered: dict[str, Any],
    candidate: dict[str, Any],
    *,
    coil_tag: str | None = None,
) -> dict[str, Any]:
    """Adapter: build a canonical record from a per-coil ``SubmittalCoilCandidate``
    dict (as produced by ``run_pdf_to_drawing_workflow``) and verify against it."""
    from coilforge.submittal import SubmittalCoilCandidate
    from coilforge.submittal.to_canonical import map_submittal_candidate_to_canonical_result

    parsed = SubmittalCoilCandidate.model_validate(candidate)
    record = map_submittal_candidate_to_canonical_result(parsed).record
    tag = coil_tag
    if tag is None and parsed.tag is not None and parsed.tag.value not in (None, ""):
        tag = str(parsed.tag.value)
    return verify_entered_values(entered, record, coil_tag=tag)


def _row(
    spec: Any,
    field_key: str,
    coilforge_value: Any,
    confidence: str | None,
    status: str | None,
    entered_value: Any,
    *,
    match: bool,
    severity: str,
    note: str,
) -> dict[str, Any]:
    return {
        "field_key": field_key,
        "label": spec.label,
        "section": spec.section,
        "coilforge_value": coilforge_value,
        "coilforge_confidence": confidence,
        "coilforge_status": status,
        "entered_value": entered_value,
        "match": match,
        "severity": severity,
        "note": note,
    }
