"""Drain-pan option parsing (E1) + the misdetection it must stay away from (E2).

The two real 22-token codes here were read out of live submittals on 2026-08-05
(2755 Terra H, 2948 Terra V) — they are the reason the feature is buildable at all.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from coilforge.submittal.coilmaster_drawing_extract import (  # noqa: E402
    detect_product_and_size,
)
from coilforge.submittal.model_code import (  # noqa: E402
    drain_pan_option_from_model_code,
    find_model_code_run,
)

# Real codes, from real submittals.
TERRA_H = "TR_C_012_I_R_1_H11_21_XSXS_V_XX_X_X_X_XX_XX_X_XXX_XX_X_X_X"
TERRA_V = "TV_B_006_I_L_1_H10_11_XSXS_V_XX_X_X_X_XX_XX_X_XXX_XX_X_X_X"


# --------------------------------------------------------------------------- #
# the parse
# --------------------------------------------------------------------------- #
def test_real_terra_h_code_yields_its_drain_pan_option():
    option, reason = drain_pan_option_from_model_code(TERRA_H)
    assert option == "D1"  # token '21' -> control qty 2, pan type 1
    assert "index 7" in reason and "21" in reason


def test_the_option_is_read_from_the_second_digit_not_the_first():
    # '21' and '31' differ only in control quantity and must give the same pan.
    for token, expected in (("11", "D1"), ("21", "D1"), ("32", "D2"), ("13", "D3")):
        code = f"TR_C_012_I_R_1_H11_{token}_XSXS_V_XX_X_X"
        assert drain_pan_option_from_model_code(code)[0] == expected, token


def test_a_code_embedded_in_a_line_of_text_is_found():
    line = f"3   CDXC-1   DXC Cooling   {TERRA_H}   LH   208/3/60"
    assert drain_pan_option_from_model_code(line)[0] == "D1"


def test_the_longest_run_wins_when_several_appear():
    text = f"TR_C_012_I_R  and  {TERRA_H}"
    assert len(find_model_code_run(text).split("_")) == 22


# --------------------------------------------------------------------------- #
# every refusal is specific
# --------------------------------------------------------------------------- #
def test_terra_v_is_refused_with_its_own_reason():
    option, reason = drain_pan_option_from_model_code(TERRA_V)
    assert option is None, (
        "Terra V pan width is keyed by unit SIZE — reading a D-option off its code would "
        "hand a Terra H width to a vertical unit"
    )
    assert "keyed by unit size" in reason


def test_a_short_code_has_no_drain_pan_token():
    option, reason = drain_pan_option_from_model_code("TR_C_012_I_R_1_H11")
    assert option is None and "not present" in reason


def test_a_non_two_digit_token_is_refused():
    option, reason = drain_pan_option_from_model_code(
        "TR_C_012_I_R_1_H11_X_XSXS_V_XX"
    )
    assert option is None and "always exactly two digits" in reason


def test_an_out_of_range_pan_digit_is_refused_rather_than_clamped():
    for token in ("10", "24", "39"):
        option, reason = drain_pan_option_from_model_code(
            f"TR_C_012_I_R_1_H11_{token}_XSXS_V_XX"
        )
        assert option is None, token
        assert "not one of 1/2/3" in reason


def test_text_without_a_model_code_is_refused():
    assert drain_pan_option_from_model_code("CDXC-1 DXC Cooling LH")[0] is None
    assert drain_pan_option_from_model_code("")[0] is None
    assert drain_pan_option_from_model_code(None)[0] is None


def test_the_short_schedule_code_alone_is_not_enough():
    # 'TR_C_012' is what row.model holds today; it carries no pan token.
    option, reason = drain_pan_option_from_model_code("TR_C_012")
    assert option is None
    assert "no full underscore-joined" in reason


# --------------------------------------------------------------------------- #
# E2: why the full code must stay OUT of the detection path
# --------------------------------------------------------------------------- #
def test_the_full_code_breaks_product_detection_in_two_different_ways():
    """Pinning the defect this feature has to route around.

    ``detect_product_and_size``'s Terra regexes end in ``\\b``, which cannot match a code
    that continues with ``_``. What happens next depends on the code's INNER size token,
    so the two Terra formats fail differently — which is why one regression case is not
    enough:

      * Terra V's inner ``H10`` IS a valid Ventum H size -> confidently WRONG product line
      * Terra H's inner ``H11`` is NOT -> product line unresolved

    A wrong line picks the wrong R-074 casing, the wrong R-076 sizes and the wrong
    drain-pan widths, and nothing in the UI says so.
    """
    assert detect_product_and_size(TERRA_V) == ("VENTUM_H", "H10")
    assert detect_product_and_size(TERRA_H) == (None, None)

    # The short forms — what the cover row actually carries — are correct.
    assert detect_product_and_size("TR_C_012") == ("TERRA H", "012")
    assert detect_product_and_size("TV_B_006") == ("TERRA V", "006")


def test_model_code_run_never_returns_the_short_form():
    """The dedicated field holds the FULL code; the short code keeps its own field.

    If this ever returned 'TR_C_012', a caller storing the result would be storing
    something safe to detect on, and the separation this module exists to enforce would
    quietly stop mattering.
    """
    assert find_model_code_run("TR_C_012") is None
    assert find_model_code_run(TERRA_H) == TERRA_H
