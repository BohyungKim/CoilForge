"""E2: the option reaches the consumers WITHOUT the full model code poisoning detection.

The regression this guards is subtle. Reading the drain-pan option means handling the full
22-token model code, and the obvious place to put it — `row.model` / `candidate.notes` —
is the one place it must never go, because `detect_product_and_size` mis-reads it.

Asserting on `detect_product_and_size` directly would be hollow: it is a pure cached
function of its argument, so passing it the short code proves nothing about where the code
is stored. These tests therefore assert on the END surfaces — the coil dicts and fit inputs
that actually feed the checklist and the fit report.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

pytest.importorskip("yaml")

from coilforge.checklist.from_workflow import coil_inputs_from_candidates  # noqa: E402
from coilforge.submittal.model_code import (  # noqa: E402
    drain_pan_option_for_unit_size,
    drain_pan_options_by_unit_size,
)
from coilforge.workflows.submittal_to_drawing import _fit_inputs_from_ctx  # noqa: E402

TERRA_H_FULL = "TR_C_012_I_R_1_H11_21_XSXS_V_XX_X_X_X_XX_XX_X_XXX_XX_X_X_X"
TERRA_V_FULL = "TV_B_006_I_L_1_H10_11_XSXS_V_XX_X_X_X_XX_XX_X_XXX_XX_X_X_X"

# A submittal's text: the cover schedule carries the SHORT code, the configuration page
# carries the full one on its own line. That layout is why the option needs a whole-document
# read, and why detection must keep seeing only the short form.
PDF_TEXT_TERRA_H = f"""
Unit Schedule
1  CDXC-1   DXC Cooling   TR_C_012   RH   208/3/60
1  RHHGRC-1 HGRC Reheat   TR_C_012   RH   208/3/60

Configuration
{TERRA_H_FULL}
"""

PDF_TEXT_TERRA_V = f"""
Unit Schedule
1  CDXC-1   DXC Cooling   TV_B_006   LH
Configuration
{TERRA_V_FULL}
"""


def _candidate(tag, category):
    return {
        "tag": {"value": tag},
        "geometry": {"finned_height": {"value": 20.0}, "finned_length": {"value": 30.0},
                     "rows_deep": {"value": 4}},
        "connections": {"suction_connection_size": {"value": 0.875}},
        "manufacturing_options": {},
        "quantity": {"value": 1},
    }


# --------------------------------------------------------------------------- #
# package-level read
# --------------------------------------------------------------------------- #
def test_the_option_is_read_from_a_realistic_submittal_layout():
    option, reason = drain_pan_option_for_unit_size(PDF_TEXT_TERRA_H, "012")
    assert option == "D1"
    assert "index 7" in reason


def test_a_terra_v_submittal_refuses_rather_than_returning_a_terra_h_option():
    option, reason = drain_pan_option_for_unit_size(PDF_TEXT_TERRA_V, "006")
    assert option is None and "keyed by unit size" in reason


def test_a_unit_without_its_own_code_never_borrows_another_units_option():
    """The correction the real 2755 submittal forced.

    That document is MULTI-unit (sizes 009 and 012) but prints only ONE full model code.
    "Exactly one distinct code means a single-unit submittal" reads as true there and
    silently hands the 012 unit's drain pan to the 009 unit. Different units can carry
    different pans, so the borrowed width is wrong with nothing on screen to say so —
    the same shape of silent error the Terra V guard exists to prevent.
    """
    text = f"{PDF_TEXT_TERRA_H}\n1 CDXC-9 DXC Cooling TR_C_009 RH"
    assert drain_pan_option_for_unit_size(text, "012")[0] == "D1"
    option, reason = drain_pan_option_for_unit_size(text, "009")
    assert option is None
    assert "no unit model code for size 009" in reason
    assert "does not borrow" in reason


def test_each_unit_gets_its_own_option_when_both_codes_are_printed():
    text = f"{PDF_TEXT_TERRA_H}\nTR_C_024_I_R_1_H11_32_XSXS_V_XX_X_X_X_XX"
    index = drain_pan_options_by_unit_size(text)
    assert index["012"][0] == "D1"
    assert index["024"][0] == "D2"


def test_two_codes_disagreeing_about_the_same_size_refuse():
    text = (
        "TR_C_012_I_R_1_H11_21_XSXS_V_XX_X_X\n"
        "TR_C_012_I_R_1_H11_23_XSXS_V_XX_X_Y"
    )
    option, reason = drain_pan_option_for_unit_size(text, "012")
    assert option is None and "disagree" in reason


def test_a_coil_without_a_resolved_size_gets_no_option():
    option, reason = drain_pan_option_for_unit_size(PDF_TEXT_TERRA_H, None)
    assert option is None and "unit size is unresolved" in reason


# --------------------------------------------------------------------------- #
# consumer 1: the fit report inputs
# --------------------------------------------------------------------------- #
def test_fit_inputs_carry_the_option_and_its_provenance():
    ctx = {"tag": "CDXC-1", "coil_category": "DX", "product_type": "TERRA H",
           "unit_size": "012"}
    fit = _fit_inputs_from_ctx(ctx, "CDXC-1", pdf_text=PDF_TEXT_TERRA_H)
    assert fit["drain_pan_option"] == "D1"
    assert fit["drain_pan_option_reason"], (
        "a width that flips a PASS/FAIL must be able to say where it came from"
    )


def test_fit_inputs_without_an_option_still_build():
    ctx = {"tag": "CDXC-1", "coil_category": "DX", "product_type": "NOVA",
           "unit_size": "C24"}
    fit = _fit_inputs_from_ctx(ctx, "CDXC-1", pdf_text="")
    assert fit["drain_pan_option"] is None


# --------------------------------------------------------------------------- #
# consumer 2: the checklist coil dicts — and the detection regression
# --------------------------------------------------------------------------- #
def test_checklist_coils_get_the_option_and_keep_the_right_product_line():
    """The end-to-end surface E2 is really about.

    If the full code had leaked into the detection path, `product_label` here would read
    VENTUM_H (Terra V) or None (Terra H) instead of the real line — and the coil would then
    be sized against the wrong R-074 casing with nothing on screen to say so.
    """
    coils, _ = coil_inputs_from_candidates(
        [_candidate("CDXC-1", "DX"), _candidate("RHHGRC-1", "HGRH")],
        pdf_text=PDF_TEXT_TERRA_H,
    )
    assert coils, "the fixture should yield coils"
    for coil in coils:
        assert coil["drain_pan_option"] == "D1"
        assert coil["product_label"] == "TERRA H", (
            f"product line poisoned by the full model code: {coil['product_label']}"
        )
        assert coil["unit_size"] == "012"


def test_documented_limitation_detection_is_rescued_by_the_short_code_not_by_design():
    """A pre-existing latent defect this work uncovered but does NOT fix.

    Detection survives the full code only because the cover schedule ALSO prints the short
    form (`TR_C_012` / `TV_B_006`), and `detect_product_and_size` finds that first. Strip
    the short form and the same document misdetects today, with no involvement from Phase E:

        Terra V, full code only -> ('VENTUM_H', 'H10')   -- confidently wrong
        Terra H, full code only -> (None, None)          -- unresolved

    The cause is the trailing ``\\b`` in `_TERRA_MODEL_RE` / `_TERRA_V_MODEL_RE`, which
    cannot match a code that continues with ``_``. Fixing it means editing an lru_cached
    function read by the template, checklist, fit and drawing paths, so it is deliberately
    out of scope here — Phase E routes AROUND the defect by keeping the full code in a
    dedicated field. This test exists so the limitation is visible and has a home when
    someone does fix it; it asserts today's behaviour, so it will fail loudly (and should
    then be rewritten) the moment the regexes are corrected.
    """
    from coilforge.submittal.coilmaster_drawing_extract import detect_product_and_size

    assert detect_product_and_size(f"Configuration\n{TERRA_V_FULL}") == ("VENTUM_H", "H10")
    assert detect_product_and_size(f"Configuration\n{TERRA_H_FULL}") == (None, None)
    # ...and the rescue that keeps real submittals correct:
    assert detect_product_and_size(f"TV_B_006 LH\n{TERRA_V_FULL}") == ("TERRA V", "006")


def test_a_terra_v_submittal_keeps_its_line_and_gets_no_option():
    coils, _ = coil_inputs_from_candidates(
        [_candidate("CDXC-1", "DX")], pdf_text=PDF_TEXT_TERRA_V
    )
    for coil in coils:
        assert coil["product_label"] == "TERRA V", (
            "the inner H10 token of a Terra V code detects as VENTUM_H — this asserts the "
            "full code never reached detection"
        )
        assert coil["drain_pan_option"] is None
