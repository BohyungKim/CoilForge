"""Direct Coil page reader: turn captured web-form text into {normalized_key: value}.

Covers both layouts the capture paths produce (inline 'Label: value' from a text
copy, and split 'Label\\nvalue' from a DOM text dump), label normalization for the
parenthetical-unit labels (°F / (In) / (%)), the bare-label fallback, and the parse
coverage signal that guards against a near-empty read.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from coilforge.direct_coil.page_reader import (  # noqa: E402
    direct_coil_page_coverage,
    parse_direct_coil_page,
)

_INLINE = """DX COIL DATA
Tag: CDXC-1
Finned Height(In): 47
Finned Length(In): 120
Rows Deep: 4
Coil Hand: Left
Entering Dry Bulb(°F): 95
Entering Relative Humidity(%): 45
Return Connection Size: 0.625
Tube Material: Copper
"""

# DOM dump: label on its own line, value on the next line.
_SPLIT = """DX COIL DATA
Tag
CDXC-1
Finned Height(In)
47
Coil Hand
Left
Tube Material
Copper
"""


def test_inline_layout_reads_values() -> None:
    parsed = parse_direct_coil_page(_INLINE)
    assert parsed["finned_height_in"] == "47"
    assert parsed["finned_length_in"] == "120"
    assert parsed["rows_deep"] == "4"
    assert parsed["coil_hand"] == "Left"
    assert parsed["return_connection_size"] == "0.625"
    assert parsed["tube_material"] == "Copper"


def test_split_layout_reads_values() -> None:
    parsed = parse_direct_coil_page(_SPLIT)
    assert parsed["finned_height_in"] == "47"
    assert parsed["coil_hand"] == "Left"
    assert parsed["tube_material"] == "Copper"


def test_label_normalization_handles_units_and_degree_signs() -> None:
    parsed = parse_direct_coil_page(_INLINE)
    # Labels carrying °F / (%) still map to their canonical normalized_key.
    assert parsed["entering_dry_bulb_f"] == "95"
    assert parsed["entering_relative_humidity_pct"] == "45"


def test_bare_label_without_unit_still_matches() -> None:
    # Page renders 'Finned Height' without the '(In)' suffix -> base-label fallback.
    parsed = parse_direct_coil_page("Finned Height: 47\nCoil Hand: Right\n")
    assert parsed["finned_height_in"] == "47"
    assert parsed["coil_hand"] == "Right"


def test_single_letter_label_does_not_false_match_a_word() -> None:
    # 'Insulation: foo' must not be picked up as the 'I' dimension field.
    parsed = parse_direct_coil_page("Insulation: foam\nI: 3.5\n")
    assert parsed.get("i") == "3.5"


def test_absent_label_is_omitted_never_invented() -> None:
    parsed = parse_direct_coil_page("Coil Hand: Left\n")
    assert "finned_height_in" not in parsed
    assert parsed == {"coil_hand": "Left"}


def test_coverage_reports_read_count() -> None:
    coverage = direct_coil_page_coverage(_INLINE)
    assert coverage["fields_read"] == len(parse_direct_coil_page(_INLINE))
    assert coverage["fields_read"] >= 6
    assert coverage["comparable_label_count"] > coverage["fields_read"]
    assert "coil_hand" in coverage["found_keys"]


def test_empty_text_reads_nothing() -> None:
    assert parse_direct_coil_page("") == {}
    assert direct_coil_page_coverage("")["fields_read"] == 0
