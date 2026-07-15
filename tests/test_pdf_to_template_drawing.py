"""PDF text -> linked, populated template-first drawing."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from io import BytesIO  # noqa: E402

from coilforge.submittal.pdf_to_template_drawing import (  # noqa: E402
    pdf_text_to_template_drawing,
    slots_from_drawing_extract,
)
from coilforge.workflows.submittal_to_drawing import (  # noqa: E402
    run_pdf_to_drawing_workflow,
)

# Single-header DX drawing text (mirrors CDXC-1.pdf).
DX1_TEXT = (
    "15 FL\n12 FH13.25 CH\n18.00 CL1.50 HF 1.50 RF0.63 TF\n0.63 BF5.50 CD\n"
    "20.25 OAL1.75 RB\n2.00 O2\n0.63 R23.00 I12.75 S13.50 HD28.00 SL2\n4.50 HDx1\n"
    "1.50 1.752 Feed / 24 Pass\n13 Fins Per Inch\n"
    'RETURN CONN SIZE\n0.625" OD Header\n'
    "DX-F-S-04-13-12.00x15.00-L\nTag: CDXC-1\n"
)
COVER = "1 CDXC- 1 DXC Cooling A16_V_I_ERV LH\n"

# Multi-header DX (2 circuits) -> Header 2 (links, not seeded).
DX2_TEXT = (
    "34 FL\n26 FH27.25 CH\n37.00 CL1.50 HF 1.50 RF0.63 TF\n0.63 BF5.50 CD\n"
    "39.25 OAL1.75 RB\n2.00 O2\n1.13 R22.00 O4\n3.75 R43.00 I11.88 S1\n"
    "3.00 I33.63 S33.50 HD28.00 SL24.50 HDx1\n"
    "14 Passes per Feed\nC1: 3 Feed C2: 4 Feed\n"
    "DX-F-S-04-14-26.00x34.00-R\nTag: CDXC-2\n"
)


def test_slots_map_extracted_dims_to_slot_ids() -> None:
    from coilforge.submittal.coilmaster_drawing_extract import extract_coilmaster_drawing

    slots = slots_from_drawing_extract(extract_coilmaster_drawing(DX1_TEXT))
    assert slots["slot.CD"] == 5.5
    assert slots["slot.HDx1"] == 4.5
    assert slots["slot.FH"] == 12.0
    assert slots["slot.TAG"] == "CDXC-1"


def test_submittal_model_code_auto_populates_drawing() -> None:
    """A submittal schedule with only the model code "TR_C_009" (no "Terra" word)
    auto-detects TERRA H / 009 and runs the engine on feed, so the drawing
    populates without a manual product/size pick (review-aid, still overridable)."""
    ctx = {
        "coil_category": "DX", "coil_hand": "RH", "circuits": 1, "tag": "CDXC-1",
        "rows": 6, "feeds": 4, "finned_height": 22.0, "finned_length": 23.75,
        "suction_conn_size": 1.125,
    }
    cover = "Qty Tag Item Model Handing\n1 CDXC-1 DXC Cooling TR_C_009 RH"
    out = pdf_text_to_template_drawing("", cover_text=cover, header_context=ctx)

    assert out["product_size_auto_detected"] is True
    assert out["product_type"] == "TERRA H" and out["unit_size"] == "009"
    assert out["header_engine_used"] is True
    assert out["drawing_value_source"] == "logic_derived"
    # Engine actually produced dimensions (not unknown_unit_size).
    assert isinstance(out["slot_values"].get("slot.CD"), (int, float))
    assert out["export_allowed"] is False


def test_panel_mirrors_template_drawing_slots() -> None:
    """The Drawing Parameters panel is built from the SAME slot values the drawing
    renders, so the two never diverge (single source of truth)."""
    from coilforge.services.drawing_param_resolver import (
        PARAM_TO_SLOT,
        parameter_set_from_template_drawing,
    )

    out = pdf_text_to_template_drawing(DX1_TEXT, cover_text=COVER)
    assert out["header_engine_used"] is True
    params = parameter_set_from_template_drawing(out).parameters
    slots = out["slot_values"]
    for key, slot in PARAM_TO_SLOT.items():
        assert params[key].value == float(slots[slot]), f"{key} != {slot}"
    # Distributor HD (HDx1) is distinct from the return header HD and is shown.
    assert params["HDx1"].value == 4.5 and params["HD"].value != params["HDx1"].value
    # ZD is the owner-fixed constant 4.5 (review-required like every panel value).
    assert params["ZD"].value == 4.5 and params["ZD"].status == "review_required"


def test_panel_reads_review_required_before_engine_runs() -> None:
    """With no product line + unit size the engine is gated, so the drawing shows
    REVIEW REQUIRED and the panel mirrors that (no misleading numbers)."""
    from coilforge.services.drawing_param_resolver import (
        parameter_set_from_template_drawing,
    )

    ctx = {"coil_category": "DX", "coil_hand": "RH", "circuits": 1, "tag": "CDXC-1"}
    out = pdf_text_to_template_drawing("", cover_text="", header_context=ctx)
    assert out["header_engine_used"] is False
    params = parameter_set_from_template_drawing(out).parameters
    for key in ("CD", "HD", "HDx1", "SL", "I", "S", "O", "CH"):
        assert params[key].value is None
        assert params[key].review_required is True


def test_derive_endpoint_returns_aligned_parameter_set() -> None:
    """Re-deriving with a chosen product line + unit size refreshes BOTH the
    drawing and the panel from the same slot values."""
    from coilforge.workflows.submittal_to_drawing import derive_coil_template_drawing

    spec = {
        "coil_category": "DX", "coil_hand": "LH", "circuits": 1, "tag": "CDXC-1",
        "rows": 4, "feeds": 2, "finned_height": 12.0, "finned_length": 15.0,
        "suction_conn_size": 0.625, "product_type": "NOVA", "unit_size": "A16",
    }
    result = derive_coil_template_drawing(spec)
    assert "drawing_parameter_set" in result
    params = result["drawing_parameter_set"]["parameters"]
    assert params["CD"]["value"] == result["slot_values"]["slot.CD"]
    assert params["HDx1"]["value"] == result["slot_values"]["slot.HDx1"]


def test_dx1_pdf_links_and_renders() -> None:
    out = pdf_text_to_template_drawing(DX1_TEXT, cover_text=COVER)
    assert out["extracted"]["coil_category"] == "DX"
    assert out["extracted"]["circuits"] == 1
    assert out["unit_size"] == "A16" and out["product_type"] == "NOVA"
    assert out["template_id"] == "coilmaster_dx_lh_header1"
    assert out["generation_allowed"] is True
    assert out["svg"] and "5.5" in out["svg"]
    assert out["export_allowed"] is False


def test_dx2_links_and_renders_seeded_header2() -> None:
    out = pdf_text_to_template_drawing(DX2_TEXT)
    assert out["extracted"]["circuits"] == 2 and out["extracted"]["feeds"] == 7
    assert out["template_id"] == "coilmaster_dx_rh_header2"
    assert out["template_found"] is True
    # DX Header 2 RH is now seeded (from EZC-0011's real EZ drawing) and renders.
    assert out["generation_allowed"] is True
    assert out["svg"] and "5.5" in out["svg"]
    assert out["export_allowed"] is False
    assert out["slot_values"]["slot.CD"] == 5.5
    assert out["slot_values"]["slot.HDx1"] == 4.5


def test_dx1_dimensions_are_logic_derived_and_validated() -> None:
    """PDF inputs -> documented engine/formula logic DERIVES the dimensions
    (authoritative); the as-built drawing is read only to validate."""
    out = pdf_text_to_template_drawing(DX1_TEXT, cover_text=COVER)
    assert out["drawing_value_source"] == "logic_derived"
    assert out["header_engine_used"] is True
    assert out["product_type"] == "NOVA" and out["unit_size"] == "A16"
    src = out["slot_sources"]
    # Engine-rule + recovered-formula dimensions match the as-built drawing.
    assert src["slot.CD"]["source"] == "engine_rule" and src["slot.CD"]["validation"] == "match"
    assert src["slot.CH"]["source"] == "recovered_formula" and src["slot.CH"]["validation"] == "match"
    assert src["slot.HDx1"]["validation"] == "match" and src["slot.HDx1"]["value"] == 4.5
    assert src["slot.S1"]["value"] == 2.75  # S = CD/(circuits+1)
    # The one documented-uncertain value is flagged, never silently wrong.
    assert out["validation_mismatches"].get("slot.OAL", "").startswith("mismatch")
    assert "5.5" in out["svg"]


def test_logic_reproduces_reference_coil_within_gate() -> None:
    """Ground truth: the documented logic reproduces the EZC-0001 as-built dims."""
    from coilforge.services.direct_coil_drawing_pipeline import build_drawing_slots

    slots, _ = build_drawing_slots(
        coil_type="DX", product_type="NOVA", unit_size="A16",
        rows=4, feeds=2, circuits=1, suction_conn_size=0.625,
        finned_height=12.0, finned_length=15.0,
    )
    expected = {
        "slot.CD": 5.5, "slot.TF": 0.625, "slot.BF": 0.625, "slot.HDx1": 4.5,
        "slot.HD2": 3.5, "slot.SL2": 8.0, "slot.I1": 3.0, "slot.O2": 2.0,
        "slot.CH": 13.25, "slot.CL": 18.0, "slot.S1": 2.75,
    }
    for slot, value in expected.items():
        assert abs(float(slots[slot]) - value) < 0.02, f"{slot}: {slots.get(slot)} != {value}"


# Two-circuit DX, LH, WITH a return-conn-size line so the R-022 return_spacing
# list fires and every per-header position is logic-derived (not as-built).
DX2_LH_CONN_TEXT = (
    "34 FL\n26 FH27.25 CH\n37.00 CL1.50 HF 1.50 RF0.63 TF\n0.63 BF5.50 CD\n"
    "39.25 OAL1.75 RB\n"
    'RETURN CONN SIZE\n1.125" OD Header\n'
    "C1: 3 Feed C2: 4 Feed\n"
    "DX-F-S-04-14-26.00x34.00-L\nTag: CDXC-2\n"
)
DX2_LH_COVER = "1 CDXC- 2 DXC Cooling A16_V_I_ERV LH\n"


def test_multi_header_positions_are_logic_derived() -> None:
    """A 2-circuit DX derives BOTH header pairs (H1/H2 and H3/H4) from the engine
    + recovered formulas, not the as-built fallback. Closes the multi-header gap:
    the per-circuit loop emits I3/S3/HDx3/O4/R4/HD4/SL4 from engine constants,
    the k*CD/(circuits+1) S-formula, and the R-022 return_spacing list."""
    out = pdf_text_to_template_drawing(DX2_LH_CONN_TEXT, cover_text=DX2_LH_COVER)
    assert out["extracted"]["circuits"] == 2
    assert out["template_id"] == "coilmaster_dx_lh_header2"
    assert out["drawing_value_source"] == "logic_derived"
    src = out["slot_sources"]

    # No per-header position falls back to the as-built reading.
    per_header = [
        "slot.I1", "slot.S1", "slot.HDx1", "slot.O2", "slot.R2", "slot.HD2", "slot.SL2",
        "slot.I3", "slot.S3", "slot.HDx3", "slot.O4", "slot.R4", "slot.HD4", "slot.SL4",
    ]
    for slot in per_header:
        assert slot in src, f"{slot} not derived"
        assert src[slot]["source"] in {"engine_rule", "recovered_formula"}, (
            f"{slot} fell back to {src[slot]['source']}"
        )

    # Constants repeat across same-parity headers.
    sv = out["slot_values"]
    assert sv["slot.I3"] == sv["slot.I1"] and sv["slot.HDx3"] == sv["slot.HDx1"]
    assert sv["slot.O4"] == sv["slot.O2"] and sv["slot.HD4"] == sv["slot.HD2"]
    assert sv["slot.SL4"] == sv["slot.SL2"]
    # S = k*CD/(circuits+1); CD=5.5 -> S1=1.8333, S3=3.6667.
    assert abs(float(sv["slot.S1"]) - 5.5 / 3) < 0.01
    assert abs(float(sv["slot.S3"]) - 2 * 5.5 / 3) < 0.01
    # R = return_spacing R-022 list: D=1.125 -> R2=1.125, R4=2D+1.5=3.75.
    assert abs(float(sv["slot.R2"]) - 1.125) < 0.01
    assert abs(float(sv["slot.R4"]) - 3.75) < 0.01


def test_panel_surfaces_logical_header2_for_two_circuit_dx() -> None:
    """The Drawing Parameters panel exposes the second header assembly with LOGICAL
    keys (I2/S2/O2/R2/HD2/ZD2), translated from the engine's parity slots (I3/O4...).
    Parity ids never leak to the panel; values stay review-aid only."""
    from coilforge.services.drawing_param_resolver import (
        parameter_set_from_template_drawing,
    )

    out = pdf_text_to_template_drawing(DX2_LH_CONN_TEXT, cover_text=DX2_LH_COVER)
    pset = parameter_set_from_template_drawing(out, circuits=out["extracted"]["circuits"])
    params = pset.parameters

    sv = out["slot_values"]
    # logical header-2 keys present; parity ids absent from the panel.
    for key in ("I2", "S2", "O2", "R2", "HD2", "ZD2"):
        assert key in params, key
        assert params[key].status == "review_required"
    assert "I3" not in params and "O4" not in params
    # header-2 values mirror the parity slots (circuit 2 = slot ids 3/4).
    assert params["I2"].value == float(sv["slot.I3"])
    assert params["S2"].value == float(sv["slot.S3"])
    assert params["O2"].value == float(sv["slot.O4"])
    assert params["R2"].value == float(sv["slot.R4"])
    assert params["HD2"].value == float(sv["slot.HD4"])
    # ZD constant on both header assemblies; safety flag preserved.
    assert params["ZD"].value == 4.5 and params["ZD2"].value == 4.5
    assert pset.export_allowed is False


# --- Real-submittal path: a submittal has no embedded as-built CoilMaster
# drawing, so classification (coil type / hand / header qty / HGBP) must arrive
# via header_context and drive template selection — not the model-number parse. ---


def test_submittal_classification_drives_template_selection() -> None:
    """With no drawing text, the caller-resolved classification links the coil to
    its template and is surfaced (the fields that actually pick a template)."""
    out = pdf_text_to_template_drawing(
        "",
        header_context={
            "coil_category": "DX",
            "coil_hand": "RH",
            "circuits": 1,
            "tag": "CDXC-1",
        },
    )
    assert out["template_found"] is True
    assert out["template_id"] == "coilmaster_dx_rh_header1"
    assert out["extracted"]["coil_category"] == "DX"
    assert out["extracted"]["hand"] == "RH"
    assert out["extracted"]["header_type"] == "Header 1"
    assert out["extracted"]["tag"] == "CDXC-1"  # candidate tag wins over unit tag
    assert out["export_allowed"] is False


def test_submittal_hgrh_rh_links_header1() -> None:
    out = pdf_text_to_template_drawing(
        "", header_context={"coil_category": "HGRH", "coil_hand": "RH", "circuits": 1}
    )
    assert out["template_found"] is True
    assert out["template_id"] == "coilmaster_hgrh_rh_header1"


def test_submittal_hgbp_special_feature_links_hgbp_template() -> None:
    """A best-effort HGBP signal routes to the HGBP template (header ignored)."""
    out = pdf_text_to_template_drawing(
        "",
        header_context={"coil_category": "DX", "coil_hand": "LH", "special_feature": "HGBP"},
    )
    assert out["template_found"] is True
    assert out["template_id"] == "coilmaster_dx_lh_hgbp"
    assert out["extracted"]["special_feature"] == "HGBP"


def test_submittal_links_but_leaves_dims_review_required_without_product_unit() -> None:
    """Link + classify, but dimensions stay REVIEW REQUIRED when no product line +
    unit size is known — the engine is gated, never fed invented context."""
    out = pdf_text_to_template_drawing(
        "",
        header_context={
            "coil_category": "DX",
            "coil_hand": "RH",
            "circuits": 1,
            "rows": 6,
            "feeds": 4,
            "finned_height": 12.0,
            "finned_length": 22.0,
        },
    )
    assert out["template_found"] is True
    assert out["header_engine_used"] is False
    assert out["drawing_value_source"] == "as_built_fallback"


def test_submittal_path_suppresses_garbage_as_built_and_maps_known_geometry() -> None:
    """Part A + B: on the submittal path (no genuine drawing) the as-built text
    parse is noise, so it is NOT used to fill slots; the genuinely-known geometry
    (FH/FL/ROWS/circuiting) is mapped review-required instead."""
    out = pdf_text_to_template_drawing(
        "",
        header_context={
            "coil_category": "DX",
            "coil_hand": "RH",
            "circuits": 1,
            "rows": 6,
            "feeds": 4,
            "finned_height": 12,
            "finned_length": 22,
        },
    )
    sv = out["slot_values"]
    src = out["slot_sources"]
    # Part B: known geometry mapped as submittal_input, review-required.
    assert sv["slot.FH"] == 12 and src["slot.FH"]["source"] == "submittal_input"
    assert sv["slot.FL"] == 22 and src["slot.FL"]["validation"] == "review_required"
    assert sv["slot.ROWS"] == 6 and src["slot.ROWS"]["source"] == "submittal_input"
    assert sv["slot.CIRCUITING"] == "4 Feed"
    # Part A: no spurious as-built dims leaked in (engine gated, no real drawing).
    assert "slot.CD" not in sv
    assert not any(meta["source"] == "as_built_fallback" for meta in src.values())


def test_derive_coil_template_drawing_unlocks_engine_dims() -> None:
    """Part C: choosing a product line + unit size runs the engine, so the header
    dimensions become logic-derived instead of REVIEW REQUIRED."""
    from coilforge.workflows import derive_coil_template_drawing

    out = derive_coil_template_drawing(
        {
            "coil_category": "DX",
            "coil_hand": "RH",
            "circuits": 1,
            "tag": "CDXC-1",
            "rows": 6,
            "feeds": 4,
            "finned_height": 12,
            "finned_length": 22,
            "product_type": "NOVA",
            "unit_size": "A16",
        }
    )
    assert out["template_found"] is True
    assert out["template_id"] == "coilmaster_dx_rh_header1"
    assert out["header_engine_used"] is True
    assert out["drawing_value_source"] == "logic_derived"
    sv = out["slot_values"]
    assert sv["slot.TF"] == 0.625 and sv["slot.BF"] == 0.625
    assert sv["slot.HDx1"] == 4.5 and sv["slot.HD2"] == 3.5
    assert out["export_allowed"] is False


def test_product_size_options_lists_the_four_product_lines() -> None:
    from coilforge.submittal.coilmaster_drawing_extract import product_size_options

    options = product_size_options()
    assert set(options) == {"NOVA", "TERRA H", "TERRA V", "VENTUM_H", "VENTUM_PLUS"}
    assert "A16" in options["NOVA"]
    # Terra H and Terra V have DIFFERENT size sets (John 2026-06-29): Terra V adds
    # 060/072/084/100 on top of the shared 9; Terra H stays at 9.
    assert len(options["TERRA H"]) == 9
    assert len(options["TERRA V"]) == 13
    assert set(options["TERRA H"]).issubset(set(options["TERRA V"]))
    assert "009" in options["TERRA H"]
    assert "060" in options["TERRA V"] and "060" not in options["TERRA H"]
    # Zero-padded 3-digit tokens, never the bare integers (John 2026-06-15).
    assert "9" not in options["TERRA H"]


def test_terra_picker_labels_resolve_to_product_family_and_variant() -> None:
    from coilforge.submittal.coilmaster_drawing_extract import resolve_product_line

    # Terra split phase 2: the family is now the first-class TERRA_H / TERRA_V; the
    # terra_variant still carries the H-C sub-variant. "TERRA V" -> Terra V; others unchanged.
    assert resolve_product_line("TERRA H") == ("TERRA_H", "TERRA_H_C")
    assert resolve_product_line("TERRA V") == ("TERRA_V", "TERRA_V")
    assert resolve_product_line("TERRA") == ("TERRA_H", "TERRA_H_C")
    assert resolve_product_line("NOVA") == ("NOVA", None)
    assert resolve_product_line(None) == (None, None)


def test_terra_v_picker_selection_drives_engine_variant() -> None:
    """Picking TERRA V drives terra_variant=TERRA_V so the Terra-V-only HGRH rule
    (R-046) fires with its SOP values (supply I/O=2.75, supply SL=5, return SL=12);
    TERRA H (resolved H C) keeps the generic Terra values. John 2026-06-28."""
    from coilforge.schemas.header_prepopulate import ProductFamily, TerraVariant
    from coilforge.services.direct_coil_drawing_pipeline import build_header_request
    from coilforge.services.header_prepopulate_engine import prepopulate

    req_v = build_header_request(
        coil_type="HGRH", product_type="TERRA V", unit_size="024", feeds=2, circuits=2
    )
    assert req_v.product_type == ProductFamily.TERRA_V  # phase 2: first-class family
    assert req_v.terra_variant == TerraVariant.TERRA_V
    values_v = prepopulate(req_v).values
    assert values_v["supply_io"].value == 2.75  # R-046 (SOP, HIGH)
    assert values_v["supply_sl"].value == 5
    assert values_v["return_sl"].value == 12

    req_h = build_header_request(
        coil_type="HGRH", product_type="TERRA H", unit_size="024", feeds=2, circuits=2
    )
    assert req_h.product_type == ProductFamily.TERRA_H  # phase 2: first-class family
    assert req_h.terra_variant == TerraVariant.TERRA_H_C
    values_h = prepopulate(req_h).values
    assert values_h["supply_io"].value == 2  # R-040b (Terra H/H C, unchanged)
    assert values_h["return_sl"].value == 10  # R-045b (Terra H/H C, unchanged)


# --- Right-side specification panel: submittal-stated materials / fins / weight /
# circuiting / connection map review-required, independent of the engine gate. ---


def test_submittal_panel_values_map_review_required() -> None:
    out = pdf_text_to_template_drawing(
        "",
        cover_text="Unit Type: Terra Horizontal (Ceiling Hung) Model: TR_C_009",
        header_context={
            "coil_category": "DX",
            # LH = the seeded DX Header-1 template. (RH is the mirror pair, whose
            # generation is now disabled, so it would not render an SVG to assert on.)
            "coil_hand": "LH",
            "circuits": 1,
            "tag": "CDXC-1",
            "panel": {
                "tube_material": "0.016 Copper",
                "tube_surface": "Smooth",
                "fin_material": "0.0075 Aluminium",
                "fin_surface": "Flat",
                "fins_per_inch": 11,
                "dry_weight": 35.25,
                "internal_volume": 741.87,
                "feeds": 4,
                "circuits": 1,
                "conn_size": 1.125,
            },
        },
    )
    sv, src = out["slot_values"], out["slot_sources"]
    assert sv["slot.TUBE_MATERIAL"] == "0.016 Copper"
    assert sv["slot.TUBE_MATERIAL_2"] == "Smooth"
    assert sv["slot.FIN_MATERIAL"] == "11 FPI"
    assert sv["slot.FIN_MATERIAL_2"] == "0.0075 Aluminium"
    assert sv["slot.FIN_MATERIAL_3"] == "Flat"
    assert sv["slot.DRY_WEIGHT"] == "35.25 Lbs. Per Coil"
    assert sv["slot.INTERNAL_VOLUME"] == "741.87 Cu. In."
    assert sv["slot.CIRCUITING"] == "4 Feed"
    assert sv["slot.RETURN_CONN_SIZE"] == '1.125"'  # DX shows the return connection
    # Every panel value is submittal-stated and review-required — never silently
    # treated as engine-derived/confirmed.
    for slot in ("slot.TUBE_MATERIAL", "slot.FIN_MATERIAL", "slot.DRY_WEIGHT", "slot.INTERNAL_VOLUME", "slot.RETURN_CONN_SIZE"):
        assert src[slot]["source"] == "submittal_input"
        assert src[slot]["validation"] == "review_required"
    # The "TR_C_009" model code now AUTO-DETECTS the product line + unit size
    # (TERRA H / 009) and runs the engine on feed (review-aid, still overridable);
    # because they are resolved, no separate review-required suggestion is emitted.
    assert out["product_size_auto_detected"] is True
    assert out["product_type"] == "TERRA H" and out["unit_size"] == "009"
    assert out["suggested_product_type"] is None
    assert "0.016 Copper" in out["svg"]


def test_hgrh_panel_maps_supply_connection_slot() -> None:
    """An HGRH coil's connection maps to the SUPPLY_CONN_SIZE slot the HGRH
    template exposes (the DX RETURN_CONN_SIZE slot does not exist there)."""
    out = pdf_text_to_template_drawing(
        "",
        header_context={
            "coil_category": "HGRH",
            "coil_hand": "RH",
            "circuits": 1,
            "panel": {"conn_size": 0.625, "fin_surface": "Sine", "feeds": 1, "circuits": 1},
        },
    )
    sv = out["slot_values"]
    assert sv["slot.SUPPLY_CONN_SIZE"] == '0.625"'
    assert sv["slot.FIN_MATERIAL_3"] == "Sine"
    assert sv["slot.CIRCUITING"] == "1 Feed"


def test_sunction_typo_is_read_as_connection_size() -> None:
    """Oxygen8 submittals mis-spell 'Suction' as 'Sunction'; the connection size
    must still be extracted (else RETURN/SUPPLY CONN SIZE renders blank)."""
    from coilforge.submittal import pdf_intake as intake

    page = intake._TextPage(page_number=1, text="Coil\nSunction Size (in): 0.625\n")
    captured = {
        line.source_key.lower(): line.source_value
        for line in intake._extract_detail_lines_from_page(page)
    }
    assert any("return" in key and "connection" in key for key in captured), captured
    conn_key = next(key for key in captured if "return" in key and "connection" in key)
    assert captured[conn_key] == "0.625"


def test_header_material_defaults_to_type_l_copper_review_required() -> None:
    """Header material is not on the submittal; default to the locked-evidence
    norm 'Type L Copper' as a REVIEW-REQUIRED default (not a confirmed value)."""
    out = pdf_text_to_template_drawing(
        "",
        header_context={"coil_category": "HGRH", "coil_hand": "RH", "circuits": 1, "panel": {}},
    )
    assert out["slot_values"]["slot.HEADER_MATERIAL"] == "Type L Copper"
    src = out["slot_sources"]["slot.HEADER_MATERIAL"]
    assert src["source"] == "review_default"
    assert src["validation"] == "review_required"


def test_intentional_mistake_in_as_built_is_flagged_not_silently_accepted() -> None:
    """Mapping-function validation: corrupt the as-built CD to a deliberately wrong
    value. The logic-derived value must still win (authoritative) and the
    discrepancy must be surfaced as a mismatch — never silently overwritten."""
    corrupted = DX1_TEXT.replace("0.63 BF5.50 CD", "0.63 BF9.99 CD")  # wrong CD
    out = pdf_text_to_template_drawing(corrupted, cover_text=COVER)
    assert out["slot_values"]["slot.CD"] == 5.5  # engine value is authoritative
    assert out["slot_sources"]["slot.CD"]["validation"] == "mismatch:9.99"
    assert out["validation_mismatches"].get("slot.CD", "").startswith("mismatch")


def test_workflow_includes_populated_template_drawing() -> None:
    """The intake workflow surfaces a populated template_drawing for a DX1 PDF."""
    workflow = run_pdf_to_drawing_workflow(_make_text_pdf(DX1_TEXT.splitlines()))
    template_drawing = workflow["template_drawing"]
    assert "error" not in template_drawing
    assert template_drawing["template_id"] == "coilmaster_dx_lh_header1"
    assert template_drawing["generation_allowed"] is True
    assert template_drawing["svg"] and "5.5" in template_drawing["svg"]
    assert template_drawing["export_allowed"] is False
    assert template_drawing["extracted"]["tag"] == "CDXC-1"


def _make_text_pdf(lines: list[str]) -> bytes:
    """Minimal single-page text PDF (mirrors the intake test helper)."""
    text_ops = ["BT", "/F1 12 Tf", "72 720 Td"]
    for index, line in enumerate(lines):
        safe = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        if index:
            text_ops.append("0 -16 Td")
        text_ops.append(f"({safe}) Tj")
    text_ops.append("ET")
    stream = "\n".join(text_ops).encode("latin-1")
    objects = [
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n",
        b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n",
        (
            b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >> endobj\n"
        ),
        b"4 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n",
        f"5 0 obj << /Length {len(stream)} >> stream\n".encode("ascii")
        + stream
        + b"\nendstream endobj\n",
    ]
    output = BytesIO()
    output.write(b"%PDF-1.4\n")
    offsets = []
    for obj in objects:
        offsets.append(output.tell())
        output.write(obj)
    xref_offset = output.tell()
    output.write(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode("ascii"))
    for offset in offsets:
        output.write(f"{offset:010d} 00000 n \n".encode("ascii"))
    output.write(
        f"trailer << /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode(
            "ascii"
        )
    )
    return output.getvalue()
