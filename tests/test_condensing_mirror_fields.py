"""Source-contract guards for the condensing (RHHGRC/HGRH) mirror in web/app.js.

These are substring/structure assertions over the JS source — the repo has no JS test runner
(precedent: tests/test_phase2c_ui_compatibility_panel.py). They pin the SHAPE of the fix, not
the rendered result, and that limit is real: only the browser eyeball gate proves the mirror
renders correctly. What they DO buy is that the two bugs fixed on 2026-07-28 cannot silently
return, and that the ordering the never-invent guarantee depends on cannot be refactored away.
"""

from __future__ import annotations

from pathlib import Path

_APP_JS = (Path(__file__).resolve().parents[1] / "web" / "app.js").read_text(encoding="utf-8")


def _function_body(name: str) -> str:
    start = _APP_JS.index(f"function {name}(")
    brace = _APP_JS.index("{", start)
    depth = 0
    for index in range(brace, len(_APP_JS)):
        if _APP_JS[index] == "{":
            depth += 1
        elif _APP_JS[index] == "}":
            depth -= 1
            if depth == 0:
                return _APP_JS[brace : index + 1]
    raise AssertionError(f"unbalanced braces in {name}")


def test_condensing_temp_row_does_not_source_from_liquid_temp() -> None:
    """BUG A regression guard.

    The 3rd tuple element is a sourceLabel, so this row used to look up the LIQUID temperature
    and print it under a "Condensing" label — with no Liquid row on the condensing mirror to
    contradict it. A wrong refrigerant duty point on a vendor-facing screen.
    """
    assert '"Condensing Temperature(°F)", "input", "Liquid Temperature(°F)"' not in _APP_JS
    assert '["Condensing Temperature(°F)", "input"]' in _APP_JS


def test_saturated_suction_keeps_its_correct_evaporating_alias() -> None:
    # The sibling alias one line up IS correct — guard against an over-eager "fix".
    assert '"Saturated Suction Temperature(°F)", "input", "Evaporating Temperature(°F)"' in _APP_JS


def test_row_fallback_applies_when_the_field_exists_but_is_unmapped() -> None:
    """BUG B regression guard: a declared default must not be dead."""
    body = _function_body("renderDcInputRow")
    assert "fieldIsUsable" in body and "useFallback" in body
    assert '!== "unmapped"' in body
    # A fallback is a review default, never promoted to ready.
    assert '"review_required"' in body


def test_condensing_system_type_has_no_invented_default() -> None:
    # case_006's RHHGRC-1 is "Dual-Circuit Face Split"; the old "Single-Circuit" default was
    # wrong on a real coil and only became visible once BUG B was fixed.
    assert '"System Type", "select", null, "Single-Circuit"' not in _APP_JS


def test_shared_fallbacks_reach_condensing_but_never_water() -> None:
    body = _function_body("addCandidateFallbackFields")
    assert 'directCoilMirrorFormat(uiState) === "condensing"' in body
    for water in ("chilled_water", "hot_water", "pre_hot_water"):
        assert water not in body, f"{water} must stay unmapped — no seed evidence exists"


def test_dx_gate_is_kept_not_replaced_by_a_format_check() -> None:
    # directCoilMirrorFormat falls through to "dx" as a catch-all, so a format-only gate would
    # hand DX-only values to any coil it failed to classify.
    body = _function_body("addCandidateFallbackFields")
    assert "isDxPdfCandidate(candidate)" in body


def test_pinned_dx_helper_names_still_exist() -> None:
    # tests/test_phase2e_pdf_coil_intake.py asserts these three names as substrings; they are
    # kept as thin DX wrappers so the split did not cost the only coverage this path has.
    for name in (
        "addDxOptionsFallbackFields",
        "addDxAirFallbackFields",
        "addDxRefrigerantAndFoulingFallbackFields",
    ):
        assert f"function {name}(" in _APP_JS


def test_hgrh_defaults_are_applied_after_the_fallback_map() -> None:
    """The single biggest correctness risk in this change, pinned.

    addDcFieldAlias only writes when the existing entry has no mapped value. Called AFTER the
    fallbackMap loop, a default therefore loses to a genuinely extracted submittal value.
    Hoisted ABOVE it, the default would claim the slot first and the real value would be
    REJECTED — silently masking submittal data with a company default.
    """
    body = _function_body("addCandidateFallbackFields")
    assert body.index("fallbackMap.forEach") < body.index("addCondensingDefaultFallbackFields(")


def test_hgrh_defaults_use_add_not_set_alias() -> None:
    body = _function_body("addCondensingDefaultFallbackFields")
    assert "addDcFieldAlias(" in body
    assert "setDcFieldAlias(" not in body, "setDcFieldAlias would overwrite an extracted value"


def test_uncollectable_condensing_fields_are_never_invented() -> None:
    # Separate Subcooling has no extraction anywhere and both HGRH seeds leave it blank.
    for helper in (
        "addSharedConstructionFallbackFields",
        "addCondensingDefaultFallbackFields",
        "addSharedAirFallbackFields",
    ):
        assert "Separate Subcooling" not in _function_body(helper)


def test_leaving_duty_rows_are_highlighted_only_when_they_have_a_value() -> None:
    # A reheat coil is sensible-only and reports no leaving WB; an absent duty point must read
    # as plain unmapped, not as a highlighted empty box.
    body = _function_body("renderDcInputRow")
    assert "DC_DUTY_HIGHLIGHT_LABELS" in body
    assert 'status !== "unmapped"' in body
    assert "dc-control--duty" in body


def test_duty_highlight_covers_exactly_the_two_leaving_rows() -> None:
    marker = "const DC_DUTY_HIGHLIGHT_LABELS = new Set("
    declaration = _APP_JS[_APP_JS.index(marker) : _APP_JS.index(");", _APP_JS.index(marker))]
    assert "Leaving Dry Bulb" in declaration and "Leaving Wet Bulb" in declaration
    assert "Entering" not in declaration, "John asked for Leaving only"


def test_drawing_notes_ride_the_ccsi_payload_without_entering_the_field_map() -> None:
    body = _function_body("buildCcsiAutofillPayload")
    assert "drawing_notes: ccsiDrawingNotes(uiState)" in body
    notes = _function_body("ccsiDrawingNotes")
    # The paste-surface key is direct_coil_label, not label — `label` would be undefined
    # forever and emit null, which reads as "no notes" rather than as a bug.
    assert "direct_coil_label" in notes
