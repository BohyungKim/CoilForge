from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Iterable


@dataclass(frozen=True)
class EzGridBinding:
    label: str
    state_key: str
    json_paths: tuple[str, ...]
    drawing_zones: tuple[str, ...]
    effect: str
    review_status: str = "review_required_candidate"


@dataclass(frozen=True)
class EzHeaderAssembly:
    header_id: int
    role: str
    kind: str
    label_suffix: str
    header_diameter: str
    stub_length: str
    spacing: str
    offset: str
    tube_diameter: str
    connection_size: str
    source_index: int


EZ_DX_HEADER1_BINDINGS: tuple[EzGridBinding, ...] = (
    EzGridBinding(
        "ROWS",
        "rows",
        ("Inputs.Nrows", "Geometry.Nrows"),
        ("bottom_dimension_table", "right_spec_grid"),
        "Controls the ROWS bottom-table value and tube-row count summary.",
    ),
    EzGridBinding(
        "FH",
        "fin_height",
        ("Geometry.FH", "PhysicalData.finHeight"),
        ("front_view", "bottom_dimension_table"),
        "Controls the fin-pack height label and front-view fin-pack scale.",
    ),
    EzGridBinding(
        "FL",
        "fin_length",
        ("Geometry.FL", "PhysicalData.finLength"),
        ("front_view", "bottom_dimension_table"),
        "Controls the fin-pack length label and front-view fin-pack scale.",
    ),
    EzGridBinding(
        "CH",
        "casing_height",
        ("Geometry.CH",),
        ("front_view", "bottom_dimension_table"),
        "Controls casing height label and outer casing height.",
    ),
    EzGridBinding(
        "CL",
        "casing_length",
        ("Geometry.CL",),
        ("front_view", "bottom_dimension_table"),
        "Controls casing length label and outer casing width.",
    ),
    EzGridBinding(
        "CD",
        "casing_depth",
        ("Geometry.CD",),
        ("top_header_view", "bottom_dimension_table"),
        "Controls top/header-view depth label.",
    ),
    EzGridBinding(
        "TF",
        "top_flange",
        ("Geometry.TSP",),
        ("front_view", "bottom_dimension_table"),
        "Controls top flange offset label.",
    ),
    EzGridBinding(
        "BF",
        "bottom_flange",
        ("Geometry.BSP",),
        ("front_view", "bottom_dimension_table"),
        "Controls bottom flange offset label.",
    ),
    EzGridBinding(
        "RB",
        "return_bend_allowance",
        ("Geometry.RB", "Geometry.RB2"),
        ("front_view", "bottom_dimension_table"),
        "Controls return-bend/back allowance label.",
    ),
    EzGridBinding(
        "HD2",
        "return_header_diameter",
        ("Geometry.Headers[1].HD",),
        ("top_header_view",),
        "Controls return-header diameter label in the top/header view.",
    ),
    EzGridBinding(
        "HDx1",
        "distributor_header_diameter",
        ("Geometry.Headers[0].HD",),
        ("top_header_view",),
        "Controls distributor-header diameter label in the top/header view.",
    ),
    EzGridBinding(
        "SL2",
        "return_stub_length",
        ("Geometry.Headers[1].SL[0]",),
        ("top_header_view",),
        "Controls return stub/header extension length label.",
    ),
    EzGridBinding(
        "I1",
        "supply_offset_i1",
        ("Geometry.Headers[0].IO[0]",),
        ("side_connection_view",),
        "Controls supply/distributor inlet offset label.",
    ),
    EzGridBinding(
        "S1",
        "supply_spacing_s1",
        ("Geometry.Headers[0].SR",),
        ("side_connection_view",),
        "Controls supply/distributor spacing label.",
    ),
    EzGridBinding(
        "O2",
        "return_offset_o2",
        ("Geometry.Headers[1].IO[0]",),
        ("side_connection_view",),
        "Controls return-header outlet offset label.",
    ),
    EzGridBinding(
        "R2",
        "return_spacing_r2",
        ("Geometry.Headers[1].SR", "Geometry.ReturnConnectionsSize"),
        ("side_connection_view", "right_spec_grid"),
        "Controls return-header spacing/connection label.",
    ),
    EzGridBinding(
        "HF",
        "header_face",
        ("Geometry.LEP",),
        ("front_view", "bottom_dimension_table"),
        "Controls header-face offset label.",
    ),
    EzGridBinding(
        "RF",
        "return_face",
        ("Geometry.REP",),
        ("front_view", "bottom_dimension_table"),
        "Controls return-face offset label.",
    ),
    EzGridBinding(
        "OAL",
        "observed_oal",
        ("Geometry.CL + Geometry.RB2",),
        ("front_view", "bottom_dimension_table"),
        "Observed candidate only; shows EZ reference value without approving an OAL formula.",
        "observed_candidate_review_required",
    ),
    EzGridBinding(
        "HEADERS[]",
        "header_assemblies",
        ("Geometry.Headers[]",),
        ("top_header_view", "side_connection_view", "bottom_dimension_table"),
        "Controls visible distributor/return header count, suffix labels, stub geometry, and connection positions.",
    ),
)


def build_ez_dx_header1_grid(state: Any) -> dict[str, Any]:
    """Build the EZ Coil style grid spec from a review-aid DX Header 1 state."""

    values = {
        "rows": _fmt_dim(_state_value(state, "rows")),
        "x_dimension": _fmt(_state_value(state, "x_dimension", "")),
        "fin_height": _fmt_dim(_state_value(state, "fin_height")),
        "fin_length": _fmt_dim(_state_value(state, "fin_length")),
        "casing_height": _fmt_dim(_state_value(state, "casing_height")),
        "casing_length": _fmt_dim(_state_value(state, "casing_length")),
        "casing_depth": _fmt_dim(_state_value(state, "casing_depth")),
        "return_header_diameter": _fmt_dim(_state_value(state, "return_header_diameter")),
        "observed_oal": _fmt_dim(_state_value(state, "observed_oal", "REVIEW REQUIRED")),
        "return_stub_length": _fmt_dim(_state_value(state, "return_stub_length")),
        "supply_offset_i1": _fmt_dim(_state_value(state, "supply_offset_i1")),
        "supply_spacing_s1": _fmt_dim(_state_value(state, "supply_spacing_s1")),
        "return_offset_o2": _fmt_dim(_state_value(state, "return_offset_o2")),
        "return_spacing_r2": _fmt_dim(_state_value(state, "return_spacing_r2")),
        "top_flange": _fmt_dim(_state_value(state, "top_flange")),
        "bottom_flange": _fmt_dim(_state_value(state, "bottom_flange")),
        "header_face": _fmt_dim(_state_value(state, "header_face")),
        "return_face": _fmt_dim(_state_value(state, "return_face")),
        "return_bend_allowance": _fmt_dim(_state_value(state, "return_bend_allowance")),
        "distributor_header_diameter": _fmt_dim(_state_value(state, "distributor_header_diameter")),
    }
    header_assemblies = build_ez_header_assemblies(state)
    return {
        "style_id": "ez_coil_dx_header1_candidate",
        "source_case_id": _state_value(state, "source_case_id", "EZC-0001"),
        "reference_style": "EZ Coil / Coilmaster drawing page 2",
        "review_status": "review_required_no_export",
        "dimension_table": _dimension_table(values),
        "header_assemblies": [asdict(header) for header in header_assemblies],
        "header_assembly_count": len(header_assemblies),
        "header_pair_count": len(header_assemblies) // 2,
        "callouts": _state_lines(
            state,
            "drawing_callouts",
            (
                "COLLARED HOLES REQUIRED",
                "0.3125 in. MOUNTING HOLES",
                "MOUNTING HOLE SPACING: 12 in.",
                "DISTRIBUTOR 1 HAS 6\" EXTENSION",
            ),
        ),
        "right_panel_sections": _right_panel_sections(state),
        "title_cells": _title_cells(state),
        "bindings": [asdict(binding) for binding in EZ_DX_HEADER1_BINDINGS],
    }


def binding_lookup() -> dict[str, dict[str, Any]]:
    return {binding.label: asdict(binding) for binding in EZ_DX_HEADER1_BINDINGS}


def build_ez_header_assemblies(state: Any) -> list[EzHeaderAssembly]:
    raw_headers = _state_value(state, "header_assemblies", None)
    if raw_headers is None:
        raw_headers = _state_value(state, "headers", None)
    if raw_headers is not None:
        headers = [
            _normalize_header_assembly(item, index)
            for index, item in enumerate(_iter_header_items(raw_headers))
        ]
        if headers:
            return headers

    distributor_hd = _state_value(state, "distributor_header_diameter", None)
    return_hd = _state_value(state, "return_header_diameter", None)
    return [
        EzHeaderAssembly(
            header_id=1,
            role="supply",
            kind="distributor" if distributor_hd not in (None, "") else "header",
            label_suffix="1",
            header_diameter=_fmt_dim(distributor_hd or return_hd),
            stub_length=_fmt_dim(_state_value(state, "distributor_stub_length", 0.0)),
            spacing=_fmt_dim(_state_value(state, "supply_spacing_s1", "")),
            offset=_fmt_dim(_state_value(state, "supply_offset_i1", "")),
            tube_diameter=_fmt_dim(_state_value(state, "distributor_tube_diameter", "")),
            connection_size=_fmt_dim(_state_value(state, "supply_connection_size", "")),
            source_index=0,
        ),
        EzHeaderAssembly(
            header_id=2,
            role="return",
            kind="header",
            label_suffix="2",
            header_diameter=_fmt_dim(return_hd),
            stub_length=_fmt_dim(_state_value(state, "return_stub_length", "")),
            spacing=_fmt_dim(_state_value(state, "return_spacing_r2", "")),
            offset=_fmt_dim(_state_value(state, "return_offset_o2", "")),
            tube_diameter=_fmt_dim(_state_value(state, "return_tube_diameter", "")),
            connection_size=_fmt_dim(_state_value(state, "return_connection_size", "")),
            source_index=1,
        ),
    ]


def _iter_header_items(raw_headers: Any) -> list[Any]:
    if isinstance(raw_headers, dict):
        return [raw_headers]
    if isinstance(raw_headers, Iterable) and not isinstance(raw_headers, (str, bytes)):
        return [item for item in raw_headers if isinstance(item, dict)]
    return []


def _normalize_header_assembly(raw_header: dict[str, Any], index: int) -> EzHeaderAssembly:
    header_id = int(_first_present(raw_header, "header_id", "id", "ID", default=index + 1) or index + 1)
    is_supply = _boolish(_first_present(raw_header, "is_supply", "IsSupply", default=header_id % 2 == 1))
    is_distributor = _boolish(
        _first_present(raw_header, "is_distributor", "IsDistributor", default=False)
    )
    role = str(_first_present(raw_header, "role", default="supply" if is_supply else "return")).lower()
    kind = str(
        _first_present(
            raw_header,
            "kind",
            default="distributor" if is_distributor else "header",
        )
    ).lower()
    return EzHeaderAssembly(
        header_id=header_id,
        role="supply" if role.startswith("sup") else "return",
        kind="distributor" if "dist" in kind else "header",
        label_suffix=str(_first_present(raw_header, "label_suffix", default=header_id)),
        header_diameter=_fmt_dim(_first_present(raw_header, "header_diameter", "HD")),
        stub_length=_fmt_dim(_first_number(raw_header, "stub_length", "SL")),
        spacing=_fmt_dim(_first_present(raw_header, "spacing", "SR")),
        offset=_fmt_dim(_first_number(raw_header, "offset", "IO")),
        tube_diameter=_fmt_dim(_first_present(raw_header, "tube_diameter", "Diameter")),
        connection_size=_fmt_dim(_first_number(raw_header, "connection_size", "ConnectionSize")),
        source_index=index,
    )


def _first_present(raw: dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in raw and raw[key] not in (None, ""):
            return raw[key]
    return default


def _first_number(raw: dict[str, Any], *keys: str) -> Any:
    value = _first_present(raw, *keys)
    if isinstance(value, list):
        for item in value:
            if item not in (None, ""):
                return item
        return None
    return value


def _boolish(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    return False


def _dimension_table(values: dict[str, str]) -> list[dict[str, str]]:
    return [
        {"label": "ROWS", "value": values["rows"], "source_field": "rows"},
        {"label": "X", "value": values["x_dimension"], "source_field": "x_dimension"},
        {"label": "FH", "value": values["fin_height"], "source_field": "fin_height"},
        {"label": "FL", "value": values["fin_length"], "source_field": "fin_length"},
        {"label": "CH", "value": values["casing_height"], "source_field": "casing_height"},
        {"label": "CL", "value": values["casing_length"], "source_field": "casing_length"},
        {"label": "CD", "value": values["casing_depth"], "source_field": "casing_depth"},
        {
            "label": "HD",
            "value": values["return_header_diameter"],
            "source_field": "return_header_diameter",
        },
        {"label": "OAL", "value": values["observed_oal"], "source_field": "observed_oal"},
        {"label": "SL", "value": values["return_stub_length"], "source_field": "return_stub_length"},
        {"label": "I", "value": values["supply_offset_i1"], "source_field": "supply_offset_i1"},
        {"label": "S", "value": values["supply_spacing_s1"], "source_field": "supply_spacing_s1"},
        {"label": "O", "value": values["return_offset_o2"], "source_field": "return_offset_o2"},
        {"label": "R", "value": values["return_spacing_r2"], "source_field": "return_spacing_r2"},
        {"label": "TF", "value": values["top_flange"], "source_field": "top_flange"},
        {"label": "BF", "value": values["bottom_flange"], "source_field": "bottom_flange"},
        {"label": "HF", "value": values["header_face"], "source_field": "header_face"},
        {"label": "RF", "value": values["return_face"], "source_field": "return_face"},
        {
            "label": "RB",
            "value": values["return_bend_allowance"],
            "source_field": "return_bend_allowance",
        },
    ]


def _right_panel_sections(state: Any) -> list[dict[str, Any]]:
    fpi = _fmt(_state_value(state, "fin_density_fpi"))
    return [
        {
            "heading": "TUBE MATERIAL",
            "lines": _state_lines(state, "tube_material_display", ("0.375 x 0.016", "Copper Smooth")),
        },
        {
            "heading": "FIN MATERIAL",
            "lines": _state_lines(
                state,
                "fin_material_display",
                (f"{fpi} Fins Per Inch", "0.0075 Aluminum", "Sine Wave"),
            ),
        },
        {
            "heading": "CASING MATERIAL",
            "lines": _state_lines(state, "casing_material_display", ("16 Ga.", "Galvanized Steel")),
        },
        {
            "heading": "COIL TUBE FACE",
            "lines": _state_lines(
                state,
                "coil_tube_face_display",
                (f"Tube Face = {_fmt(_state_value(state, 'fin_height'))}",),
            ),
        },
        {
            "heading": "CIRCUITING",
            "lines": _state_lines(
                state,
                "circuiting_display_lines",
                (str(_state_value(state, "circuiting_display", "REVIEW REQUIRED")), "0 Dropped Tubes"),
            ),
        },
        {
            "heading": "HEADER MATERIAL",
            "lines": _state_lines(state, "header_material_display", ("Type L Copper",)),
        },
        {
            "heading": "DISTRIBUTORS",
            "lines": _state_lines(
                state,
                "distributors_display",
                ("(1)501-2-3/16-1.5(0 ASC)", "OD:5/8"),
            ),
        },
        {
            "heading": "RETURN CONN SIZE",
            "lines": _state_lines(
                state,
                "return_conn_size_display",
                (
                    f"{_fmt(_state_value(state, 'return_connection_size'))}\" OD Header",
                    f"{_fmt(_state_value(state, 'return_connection_size'))}\" SWT-Copper",
                ),
            ),
        },
        {
            "heading": "FASTENER TYPE",
            "lines": _state_lines(state, "fastener_type_display", ("Bolts",)),
        },
        {
            "heading": "DRY WEIGHT",
            "lines": _state_lines(state, "dry_weight_display", ("20.5 Lbs. Per Coil",)),
        },
        {
            "heading": "INTERNAL VOLUME",
            "lines": _state_lines(state, "internal_volume_display", ("0.06 ft3 Per Coil",)),
        },
    ]


def _title_cells(state: Any) -> dict[str, str]:
    return {
        "coil_id": str(_state_value(state, "coil_id", "")),
        "tag": str(_state_value(state, "coil_name", "")),
        "wo_number": str(_state_value(state, "wo_number", "")),
        "item": str(_state_value(state, "item_number", "001")),
        "revision": str(_state_value(state, "revision", "A")),
        "quantity": str(_state_value(state, "quantity", "1")),
        "created_by": str(_state_value(state, "created_by", "CoilForge Review")),
        "model_number": str(_state_value(state, "model_number", "")),
        "notes": str(_state_value(state, "drawing_notes", _first_note(state))),
    }


def _state_value(state: Any, key: str, default: Any = None) -> Any:
    if hasattr(state, key):
        value = getattr(state, key)
        if value is not None:
            return value
    extra = getattr(state, "model_extra", None) or {}
    value = extra.get(key, default)
    return default if value is None else value


def _state_lines(state: Any, key: str, default: Iterable[str]) -> list[str]:
    raw = _state_value(state, key, None)
    if raw is None:
        return [str(item) for item in default]
    if isinstance(raw, str):
        return [line.strip() for line in raw.splitlines() if line.strip()]
    if isinstance(raw, Iterable):
        return [str(item).strip() for item in raw if str(item).strip()]
    return [str(raw).strip()] if str(raw).strip() else [str(item) for item in default]


def _first_note(state: Any) -> str:
    notes = _state_value(state, "notes", [])
    if isinstance(notes, list) and notes:
        return str(notes[0])
    return "Review aid only. Not for manufacturing."


def _fmt(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, int):
        return f"{value}"
    if isinstance(value, float):
        text = f"{value:.4f}".rstrip("0").rstrip(".")
        return text if text else "0"
    return str(value)


def _fmt_dim(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float)):
        rounded = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        return f"{rounded:.2f}"
    return str(value)
