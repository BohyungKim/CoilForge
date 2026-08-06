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


def test_shared_fallbacks_reach_condensing_and_water_on_separate_predicates() -> None:
    """Water coils were deliberately excluded until John released them 2026-07-28 (a real
    HWC rendered as a wall of "unmapped"). The two predicates must stay SEPARATE: the
    condensing one also drives addCondensingDefaultFallbackFields, so widening it — rather
    than adding waterCandidate — would stamp refrigerant temperatures onto a water coil.
    """
    body = _function_body("addCandidateFallbackFields")
    assert 'mirrorFormat === "condensing"' in body
    assert "waterCandidate" in body
    for water in ("chilled_water", "hot_water", "pre_hot_water", "post_hot_water"):
        assert water in body, f"{water} must reach the shared construction rules"
    # The refrigerant defaults stay keyed on condensingCandidate ALONE.
    assert "if (condensingCandidate) {\n    addCondensingDefaultFallbackFields" in body


def test_water_does_not_get_the_dx_capacity_and_face_velocity_defaults() -> None:
    """Both are unconditional setDcFieldAlias writes that run BEFORE the extracted
    fallbackMap, so on a water coil they would mask real Max Coil Performance readings:
    Total Capacity 142.31 would render as 0 and the printed Air Vel 424 would be replaced
    by the arithmetic 424.24. The water branch takes the extracted-only air subset."""
    body = _function_body("addCandidateFallbackFields")
    water_branch = body[body.index("} else if (waterCandidate) {"):]
    assert "addExtractedAirFallbackFields(fieldsByLabel" in water_branch
    assert "addSharedAirFallbackFields(fieldsByLabel" not in water_branch
    # The defaults still exist for DX/condensing, just isolated.
    defaults = _function_body("addDxReviewDefaultAirFields")
    assert "Total Capacity(MBH)(Per Coil)" in defaults
    assert "directCoilFaceVelocityField" in defaults
    # ...and the extracted-only subset must carry neither.
    extracted = _function_body("addExtractedAirFallbackFields")
    assert "Total Capacity(MBH)(Per Coil)" not in extracted
    assert "directCoilFaceVelocityField" not in extracted


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
    assert "isDcDutyLabel(label)" in body
    assert 'status !== "unmapped"' in body
    assert "dc-control--duty" in body


def test_duty_highlight_covers_exactly_the_two_leaving_rows() -> None:
    marker = "const DC_DUTY_HIGHLIGHT_LABELS = new Set("
    declaration = _APP_JS[_APP_JS.index(marker) : _APP_JS.index(");", _APP_JS.index(marker))]
    assert "Leaving Dry Bulb" in declaration and "Leaving Wet Bulb" in declaration
    assert "Entering" not in declaration, "John asked for Leaving only"


def test_duty_labels_cover_both_the_unit_and_bare_spellings() -> None:
    """normalizeDcLabel keeps the unit letter, so "Leaving Dry Bulb(°F)" normalizes to
    "leavingdrybulbf" while the calculated panel's bare "Leaving Dry Bulb" normalizes to
    "leavingdrybulb" — DIFFERENT keys. Listing only the (°F) form is what left the calculated
    panel unhighlighted (John 2026-07-29). Both spellings must stay listed.
    """
    marker = "const DC_DUTY_HIGHLIGHT_LABELS = new Set("
    declaration = _APP_JS[_APP_JS.index(marker) : _APP_JS.index(");", _APP_JS.index(marker))]
    for spelling in (
        '"Leaving Dry Bulb(°F)"',
        '"Leaving Wet Bulb(°F)"',
        '"Leaving Dry Bulb"',
        '"Leaving Wet Bulb"',
    ):
        assert spelling in declaration, f"{spelling} missing from the duty label set"


def test_calculated_panel_highlights_duty_rows_only_when_they_have_a_value() -> None:
    body = _function_body("renderDcCalculatedPanel")
    assert "isDcDutyLabel(label)" in body
    assert "dc-calculated-row--duty" in body
    # The panel carries no status class, so "has a value" is tested against the sentinel
    # strings dcCalculatedValue emits ("unmapped" / "calculated" / "review required").
    assert "DC_NON_VALUES.has(" in body


def test_calculated_duty_style_stays_theme_driven() -> None:
    css = (Path(__file__).resolve().parents[1] / "web" / "style.css").read_text(encoding="utf-8")
    rule_start = css.index(".dc-calculated-row--duty {")
    rule = css[rule_start : css.index("}", rule_start)]
    assert "var(--accent)" in rule
    # A hardcoded colour here is the light/dark bug CLAUDE.md calls out; and --accent-soft
    # does not exist, so a var() fallback would silently pin one theme's colour.
    assert "rgba(" not in rule and "#" not in rule


def test_drawing_notes_ride_the_ccsi_payload_without_entering_the_field_map() -> None:
    body = _function_body("buildCcsiAutofillPayload")
    assert "drawing_notes: ccsiDrawingNotes(uiState)" in body
    notes = _function_body("ccsiDrawingNotes")
    # The paste-surface key is direct_coil_label, not label — `label` would be undefined
    # forever and emit null, which reads as "no notes" rather than as a bug.
    assert "direct_coil_label" in notes


def test_air_flow_direction_keeps_its_declared_default() -> None:
    """The water mirror's Air Flow Direction row has NO backend field behind it, so it
    renders its declared "Horizontal" default at status review_required. It looked like a
    bug ("review required" on screen) but that is the honest state for a value the
    submittal never states. The guard that matters: no layer may register a BLOCKED field
    under this label — renderDcInputRow treats a blocked field's "review required" string
    as a usable value, which would kill the declared default (see dcControlValue)."""
    assert '["Air Flow Direction", "select", null, "Horizontal"]' in _APP_JS
    for fn in ("addSharedConstructionFallbackFields", "addExtractedAirFallbackFields",
               "addWaterFeedsFallbackField", "addCandidateFallbackFields"):
        assert "Air Flow Direction" not in _function_body(fn), fn


def test_blocked_field_loses_to_a_declared_row_default() -> None:
    """A blocked field renders the literal "review required" (dcControlValue) — not a
    value — so on a row that declares a default it must lose to that default, exactly as
    "unmapped" does. Without this the mirror's "Air Flow Direction" read "review required"
    on EVERY coil: the draft's `airflow_direction` field is blocked for all of them and
    its label normalises onto that row, leaving the declared "Horizontal" permanently
    dead (John 2026-07-29)."""
    body = _function_body("renderDcInputRow")
    assert '!== "review required"' in body
    assert '!== "unmapped"' in body
    # Rows with no declared default must be unaffected — the fallback still gates on it.
    assert "fallbackValue !== null" in body


def test_unrecognised_coil_hand_reads_not_defined_not_a_hand() -> None:
    """When the submittal states no handing the frozen drawing path falls back to LH
    artwork so a review aid still renders — but the Coil Hand ROW must not repeat that
    fallback as if it were data (John 2026-07-29). A wrong hand mirrors the entire coil,
    so this is the one field where a plausible-looking default is worse than an obvious
    blank. Add-only, so a coil whose handing WAS read keeps its real value."""
    body = _function_body("addUndefinedCoilHandField")
    assert "coil_hand_defaulted" in body
    assert "DC_COIL_HAND_UNDEFINED" in body
    assert "addDcFieldAlias(" in body
    assert "setDcFieldAlias(" not in body, "would overwrite a genuinely read handing"
    assert 'const DC_COIL_HAND_UNDEFINED = "not defined";' in _APP_JS
    # It must never read as a real value downstream (duty highlight and friends).
    assert "DC_COIL_HAND_UNDEFINED," in _APP_JS[_APP_JS.index("const DC_NON_VALUES"):][:200]
    caller = _function_body("addCandidateFallbackFields")
    assert "addUndefinedCoilHandField(fieldsByLabel)" in caller
