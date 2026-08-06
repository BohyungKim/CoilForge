from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from coilforge.services.direct_coil_drawing_pipeline import build_header_request
from coilforge.submittal.extract import (
    circuits_count_or_none,
    extract_submittal_candidate_from_structured,
)
from coilforge.submittal.pdf_intake import PDF_INTAKE_FIELD_RULES

# Junction City WWTP (0748) CDXC-1 states circuiting, not a count, in the Circuits
# cell. Left as a raw string it reached HeaderPrepopulateRequest(circuits=int|None)
# and raised, and submittal_to_drawing's `except Exception` replaced the whole
# template_drawing with {"error": ...} -- so a seeded NOVA/RH/1HD template surfaced
# in the UI as "Template not registered". The checklist crashed on the same string.
DESCRIPTOR = "3 Feeds/26 Passes/2DT"


def _circuits_field(value: str):
    candidate = extract_submittal_candidate_from_structured(
        {"COIL_TAG": "CDXC-1", "CIRCUITS": value},
        field_rules=PDF_INTAKE_FIELD_RULES,
    )
    return candidate, candidate.geometry["circuits"]


@pytest.mark.parametrize("descriptor", [DESCRIPTOR, "3 Feeds/24 Passes/0DT"])
def test_circuiting_descriptor_is_blocked_not_guessed(descriptor: str) -> None:
    # The source states no circuit count, so none is invented: value=None + a
    # blocked_reason, per the confidence gate.
    candidate, field = _circuits_field(descriptor)

    assert field.value is None
    assert field.status == "blocked"
    assert field.blocked_reason is not None
    assert "geometry.circuits" in candidate.blocked_fields


def test_blocked_circuits_keeps_the_raw_descriptor_as_evidence() -> None:
    # Blocking withholds the value; it must not destroy the source text. The
    # descriptor is the only record of the coil's stated circuiting, so it stays
    # traceable in evidence for the reviewer.
    _candidate, field = _circuits_field(DESCRIPTOR)

    assert field.source_evidence[0].source_value == DESCRIPTOR


def test_stated_circuit_count_still_maps() -> None:
    # A Circuits cell that does state a count is untouched by the block.
    _candidate, field = _circuits_field("4")

    assert field.value == 4
    assert field.status == "review_required"
    assert field.blocked_reason is None


@pytest.mark.parametrize(
    "text, expected",
    [
        (DESCRIPTOR, None),
        ("Interlaced 2 Circuits", None),  # prose -- the Coil Style path parses this
        (None, None),
        ("4", 4),
        ("2.0", 2),
    ],
)
def test_circuits_count_or_none(text: str | None, expected: int | None) -> None:
    assert circuits_count_or_none(text) == expected


def test_blocked_circuits_no_longer_raises_at_the_typed_request() -> None:
    # The original crash: a non-int circuits reaching the engine request. With the
    # cell blocked, circuits is None and the caller's existing Header-N fallback
    # supplies the header count (John 2026-07-15).
    _candidate, field = _circuits_field(DESCRIPTOR)
    circuits = field.value or 1

    request = build_header_request(
        coil_type="DX",
        product_type="NOVA",
        unit_size="H10",
        rows=5,
        circuits=circuits,
    )

    assert request.circuits == 1
