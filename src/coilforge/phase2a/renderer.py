from __future__ import annotations

import html
from typing import Any

from pydantic import BaseModel, Field

from coilforge.phase2a.models import DEFAULT_RELEASE_STATUS, DxHeader1ParameterState
from coilforge.phase2a.ez_style_grid import build_ez_dx_header1_grid
from coilforge.phase2a.validation import ValidationReport, validate_dx_header1_state


REVIEW_WATERMARK = "REVIEW AID - NOT FOR MANUFACTURING"
DEFAULT_VIEWBOX = "0 0 1600 1200"
TEMPLATE_ID = "phase2a_dx_header1_review_svg"


class SvgRenderOptions(BaseModel):
    viewBox: str = DEFAULT_VIEWBOX
    include_review_watermark: bool = True
    include_markup_layer: bool = True


class SvgRenderRequest(BaseModel):
    state: DxHeader1ParameterState
    validation_report: ValidationReport | dict[str, Any] | None = None
    render_options: SvgRenderOptions = Field(default_factory=SvgRenderOptions)


class SvgRenderResponse(BaseModel):
    svg: str
    metadata: dict[str, Any]
    warnings: list[str] = Field(default_factory=list)
    blocked_fields: list[str] = Field(default_factory=list)


def _report_from_request(request: SvgRenderRequest) -> ValidationReport:
    if isinstance(request.validation_report, ValidationReport):
        return request.validation_report
    if isinstance(request.validation_report, dict) and request.validation_report:
        return ValidationReport.model_validate(request.validation_report)
    return validate_dx_header1_state(request.state)


def _esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def _fmt(value: Any, suffix: str = "") -> str:
    if isinstance(value, float):
        text = f"{value:.4f}".rstrip("0").rstrip(".")
    else:
        text = str(value)
    return f"{text}{suffix}"


def _fmt_dimension_label(value: Any) -> str:
    if value in (None, ""):
        return ""
    if isinstance(value, (int, float)):
        return f"{float(value):.2f}"
    return str(value)


def _dimension_rows(state: DxHeader1ParameterState) -> list[tuple[str, str, str]]:
    return [
        ("ROWS", _fmt(state.rows), "rows"),
        ("FH", _fmt(state.fin_height, " in"), "fin_height"),
        ("FL", _fmt(state.fin_length, " in"), "fin_length"),
        ("FPI", _fmt(state.fin_density_fpi), "fin_density_fpi"),
        ("CH", _fmt(state.casing_height, " in"), "casing_height"),
        ("CL", _fmt(state.casing_length, " in"), "casing_length"),
        ("CD", _fmt(state.casing_depth, " in"), "casing_depth"),
        ("TF", _fmt(state.top_flange, " in"), "top_flange"),
        ("BF", _fmt(state.bottom_flange, " in"), "bottom_flange"),
        ("RB", _fmt(state.return_bend_allowance, " in"), "return_bend_allowance"),
        ("RETURN CONN", _fmt(state.return_connection_size, " in"), "return_connection_size"),
        ("OAL", "REVIEW REQUIRED", "OAL"),
    ]


def _text_line(x: int, y: int, value: str, css_class: str = "sheet-text") -> str:
    return f'<text x="{x}" y="{y}" class="{css_class}">{_esc(value)}</text>'


def _has_blockers(report: ValidationReport) -> bool:
    return report.validation_status == "blocked" or any(
        check.status == "blocked" for check in report.checks
    )


def _as_float(value: Any, default: float = 0.0) -> float:
    if value in (None, ""):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _header_hd_label(header: dict[str, Any]) -> str:
    suffix = str(header.get("label_suffix") or header.get("header_id") or "")
    if header.get("kind") == "distributor":
        return f"HDx{suffix}"
    return f"HD{suffix}"


def _header_stub_label(header: dict[str, Any]) -> str:
    suffix = str(header.get("label_suffix") or header.get("header_id") or "")
    return f"SL{suffix}"


def _header_offset_label(header: dict[str, Any]) -> str:
    suffix = str(header.get("label_suffix") or header.get("header_id") or "")
    return f"I{suffix}" if header.get("role") == "supply" else f"O{suffix}"


def _header_spacing_label(header: dict[str, Any]) -> str:
    suffix = str(header.get("label_suffix") or header.get("header_id") or "")
    return f"S{suffix}" if header.get("role") == "supply" else f"R{suffix}"


def _header_source_field(header: dict[str, Any], field: str) -> str:
    return f"header_assemblies[{int(header.get('source_index', 0))}].{field}"


def _render_header_top_view(headers: list[dict[str, Any]]) -> str:
    if not headers:
        return ""
    groups: list[str] = []
    for index, header in enumerate(headers):
        pair_index = index // 2
        is_supply = header.get("role") == "supply"
        x = 445 if is_supply else 720
        y = 338 + pair_index * 68
        width = 210
        height = 42
        hd_label = _header_hd_label(header)
        sl_label = _header_stub_label(header)
        hd_value = header.get("header_diameter") or ""
        sl_value = header.get("stub_length") or ""
        stub_width = max(48, min(150, int(_as_float(sl_value, 0.0) * 12)))
        kind_label = "DIST" if header.get("kind") == "distributor" else "HDR"
        groups.append(
            f'<g id="header.top.{_esc(str(header.get("header_id")))}" '
            f'data-source-field="Geometry.Headers[{int(header.get("source_index", index))}]">'
            f'<rect x="{x}" y="{y}" width="{width}" height="{height}" class="view-detail"/>'
            f'<line x1="{x}" y1="{y + height / 2:.1f}" x2="{x + width}" y2="{y + height / 2:.1f}" class="thin-line"/>'
            f'<path d="M {x + width - 45} {y - 12} H {x + width + 45}" class="dimension-line"/>'
            f'<text id="label.{_esc(hd_label)}.top" data-source-field="{_esc(_header_source_field(header, "HD"))}" '
            f'x="{x + width / 2 - 30:.1f}" y="{y - 16}" class="dimension-label-small">{_esc(hd_value)} {_esc(hd_label)}</text>'
            f'<text x="{x + 8}" y="{y + 28}" class="header-label-muted">{_esc(kind_label)} {int(header.get("header_id", index + 1))}</text>'
        )
        if _as_float(sl_value, 0.0) > 0:
            groups.append(
                f'<path d="M {x + width + 18} {y + height / 2:.1f} H {x + width + 18 + stub_width}" class="header-stub"/>'
                f'<text id="label.{_esc(sl_label)}.top" data-source-field="{_esc(_header_source_field(header, "SL"))}" '
                f'x="{x + width + 26}" y="{y + 16}" class="dimension-label-small">{_esc(sl_value)} {_esc(sl_label)}</text>'
            )
        groups.append("</g>")
    return "".join(groups)


def _render_header_side_view(
    headers: list[dict[str, Any]],
    *,
    rows: int,
    coil_hand: str,
    airflow_arrow: str,
    return_connection_size: Any,
) -> str:
    if not headers:
        return ""
    pair_count = max(1, (len(headers) + 1) // 2)
    face_x = 805
    face_y = 585
    face_w = 110
    face_h = 310
    left_header_x = 730
    right_header_x = 1000
    mirror = str(coil_hand).lower().startswith("right")
    supply_x = right_header_x if mirror else left_header_x
    return_x = left_header_x if mirror else right_header_x
    y_step = 0 if pair_count == 1 else min(96, 250 / (pair_count - 1))
    row_lines = []
    row_count = max(1, int(rows or 1))
    for row_index in range(row_count):
        y = face_y + 18 + row_index * ((face_h - 36) / max(1, row_count - 1))
        row_lines.append(f'<line x1="{face_x}" y1="{y:.1f}" x2="{face_x + face_w}" y2="{y:.1f}" class="thin-line"/>')

    groups = [
        f'<rect x="{face_x}" y="{face_y}" width="{face_w}" height="{face_h}" class="header-face"/>',
        "".join(row_lines),
        f'<text x="{face_x + 4}" y="{face_y - 12}" class="header-label-muted">tube rows driven by ROWS={int(rows)}</text>',
    ]
    for index, header in enumerate(headers):
        pair_index = index // 2
        is_supply = header.get("role") == "supply"
        x = supply_x if is_supply else return_x
        y = face_y + 38 + pair_index * y_step + (0 if is_supply else 34)
        hd_value = header.get("header_diameter") or ""
        sl_value = header.get("stub_length") or ""
        offset_value = header.get("offset") or ""
        spacing_value = header.get("spacing") or ""
        conn_value = header.get("connection_size") or ""
        pipe_h = max(34, min(62, int(_as_float(hd_value, 3.0) * 12)))
        pipe_w = 26
        line_start = x + pipe_w if x < face_x else x
        line_end = face_x if x < face_x else face_x + face_w
        stub_extra = min(120, max(22, int(_as_float(sl_value, 0.0) * 9)))
        stub_path = (
            f"M {line_start} {y} H {line_end}"
            if x < face_x
            else f"M {line_end} {y} H {line_start}"
        )
        label_x = x - 58 if x < face_x else x + 34
        class_suffix = "supply" if is_supply else "return"
        kind_suffix = " header-distributor" if header.get("kind") == "distributor" else ""
        hd_label = _header_hd_label(header)
        offset_label = _header_offset_label(header)
        spacing_label = _header_spacing_label(header)
        stub_label = _header_stub_label(header)
        groups.append(
            f'<g id="header.side.{_esc(str(header.get("header_id")))}" class="header-assembly header-{class_suffix}{kind_suffix}" '
            f'data-header-role="{_esc(str(header.get("role")))}" data-header-kind="{_esc(str(header.get("kind")))}">'
            f'<path d="{stub_path}" class="header-stub"/>'
            f'<rect x="{x}" y="{y - pipe_h / 2:.1f}" width="{pipe_w}" height="{pipe_h}" rx="5" class="header-pipe"/>'
            f'<circle cx="{x + pipe_w / 2:.1f}" cy="{y}" r="{max(5, _as_float(conn_value, 0.625) * 7):.1f}" class="header-connection"/>'
            f'<text id="label.{_esc(hd_label)}.side" data-source-field="{_esc(_header_source_field(header, "HD"))}" '
            f'x="{label_x}" y="{y - 18:.1f}" class="dimension-label-small">{_esc(hd_value)} {_esc(hd_label)}</text>'
            f'<text id="label.{_esc(offset_label)}.side" data-source-field="{_esc(_header_source_field(header, "IO"))}" '
            f'x="{label_x}" y="{y + 8:.1f}" class="dimension-label-small">{_esc(offset_value)} {_esc(offset_label)}</text>'
            f'<text id="label.{_esc(spacing_label)}.side" data-source-field="{_esc(_header_source_field(header, "SR"))}" '
            f'x="{label_x}" y="{y + 32:.1f}" class="dimension-label-small">{_esc(spacing_value)} {_esc(spacing_label)}</text>'
        )
        if _as_float(sl_value, 0.0) > 0:
            if x < face_x:
                sx1 = x + pipe_w
                sx2 = min(face_x - 4, sx1 + stub_extra)
            else:
                sx1 = x
                sx2 = max(face_x + face_w + 4, sx1 - stub_extra)
            groups.append(
                f'<path d="M {sx1} {y + 14} H {sx2}" class="dimension-line"/>'
                f'<text id="label.{_esc(stub_label)}.side" data-source-field="{_esc(_header_source_field(header, "SL"))}" '
                f'x="{min(sx1, sx2) + 4}" y="{y + 54:.1f}" class="dimension-label-small">{_esc(sl_value)} {_esc(stub_label)}</text>'
            )
        groups.append("</g>")

    groups.extend(
        [
            f'<text id="label.airflow.front" data-source-field="airflow_direction" x="950" y="485" class="panel-small">AIRFLOW {_esc(airflow_arrow)}</text>',
            '<path d="M 1018 475 H 925" class="dimension-line"/>',
            f'<text id="label.return_connection_size.side" data-source-field="return_connection_size" x="925" y="925" class="panel-small">RETURN {_esc(_fmt(return_connection_size, " in"))}</text>',
            f'<text id="label.coil_hand.side" data-source-field="coil_hand" x="925" y="950" class="panel-small">HAND {_esc(coil_hand)}</text>',
        ]
    )
    return "".join(groups)


def render_dx_header1_svg(request: SvgRenderRequest) -> SvgRenderResponse:
    state = request.state
    report = _report_from_request(request)
    blocked = _has_blockers(report)
    warnings = list(report.warnings)
    blocked_fields = list(report.blocked_fields)

    drawing_status = "generation_blocked" if blocked else "generated_review_aid"
    if not blocked and warnings:
        drawing_status = "generated_with_warnings"
    if blocked:
        warnings.append("SVG rendered as a blocked review surface; generation is not approved.")

    grid = build_ez_dx_header1_grid(state)
    header_assemblies = list(grid["header_assemblies"])
    dimension_values = {item["label"]: item["value"] for item in grid["dimension_table"]}
    if dimension_values.get("OAL") not in ("", "REVIEW REQUIRED"):
        warnings.append(
            "OAL is shown as an EZ reference candidate only; no CoilForge OAL formula is approved."
        )

    face_width = max(260, min(430, int(state.fin_length * 18)))
    face_height = max(170, min(300, int(state.fin_height * 16)))
    face_x = 455
    face_y = 625
    casing_width = max(face_width + 68, min(520, int(state.casing_length * 18)))
    casing_height = max(face_height + 58, min(360, int(state.casing_height * 16)))
    casing_x = face_x - 35
    casing_y = face_y - 25
    airflow_arrow = "left to right" if state.airflow_direction == "left_to_right" else state.airflow_direction

    table_x = 100
    table_y = 1005
    table_width = 1230
    table_col_width = table_width / len(grid["dimension_table"])
    dimension_cells = []
    for index, item in enumerate(grid["dimension_table"]):
        label = item["label"]
        value = item["value"]
        source_field = item["source_field"]
        x = table_x + index * table_col_width
        dimension_cells.append(
            f'<g id="label.{_esc(label)}.table" data-source-field="{_esc(source_field)}">'
            f'<rect x="{x:.2f}" y="{table_y}" width="{table_col_width:.2f}" height="28" class="table-cell"/>'
            f'<rect x="{x:.2f}" y="{table_y + 28}" width="{table_col_width:.2f}" height="28" class="table-cell"/>'
            f'<text x="{x + table_col_width / 2:.2f}" y="{table_y + 20}" class="table-code">{_esc(label)}</text>'
            f'<text x="{x + table_col_width / 2:.2f}" y="{table_y + 49}" class="table-value">{_esc(value)}</text>'
            "</g>"
        )

    callout_text = [
        _text_line(98, 96 + idx * 26, callout, "callout-text")
        for idx, callout in enumerate(grid["callouts"][:5])
    ]
    right_panel_text = []
    panel_y = 84
    for section in grid["right_panel_sections"]:
        line_count = max(1, len(section["lines"]))
        cell_height = 30 + line_count * 24
        right_panel_text.append(
            f'<g id="spec.{_esc(section["heading"]).replace(" ", "_")}">'
            f'<rect x="1320" y="{panel_y}" width="180" height="{cell_height}" class="spec-cell"/>'
            f'<text x="1330" y="{panel_y + 22}" class="spec-heading">{_esc(section["heading"])}</text>'
        )
        for line_index, line in enumerate(section["lines"]):
            right_panel_text.append(
                _text_line(1330, panel_y + 48 + line_index * 23, line, "spec-line")
            )
        right_panel_text.append("</g>")
        panel_y += cell_height

    title_cells = grid["title_cells"]
    note_line = title_cells["notes"] or "Review aid only. Not for manufacturing."
    warning_text = [
        _text_line(105, 268 + idx * 20, warning, "warning-small")
        for idx, warning in enumerate(warnings[:5])
    ]
    blocked_text = [
        _text_line(980, 268 + idx * 20, field, "blocked-small")
        for idx, field in enumerate(blocked_fields[:6])
    ]
    legacy_summary = (
        f"ROWS: {state.rows} | FPI: {_fmt(state.fin_density_fpi)} | "
        f"FH {_fmt(state.fin_height, ' in')} | FL {_fmt(state.fin_length, ' in')} | "
        f"CH {_fmt(state.casing_height, ' in')} | CL {_fmt(state.casing_length, ' in')} | "
        f"CD {_fmt(state.casing_depth, ' in')} | TF {_fmt(state.top_flange, ' in')} | "
        f"BF {_fmt(state.bottom_flange, ' in')} | RB {_fmt(state.return_bend_allowance, ' in')} | "
        f"HAND {state.coil_hand} | AIRFLOW {airflow_arrow} | "
        f"RETURN {_fmt(state.return_connection_size, ' in')} | {state.circuiting_display}"
    )
    state_extra = getattr(state, "model_extra", None) or {}
    distributor_header_diameter = _fmt_dimension_label(
        getattr(state, "distributor_header_diameter", None)
        or state_extra.get("distributor_header_diameter", "")
    )
    status_banner = (
        '<g id="label.generation_blocked">'
        '<rect x="100" y="178" width="1210" height="44" class="blocked-banner"/>'
        '<text x="118" y="207" class="blocked-banner-text">GENERATION BLOCKED - REVIEW REQUIRED</text>'
        "</g>"
        if blocked
        else ""
    )
    header_top_view = _render_header_top_view(header_assemblies)
    header_side_view = _render_header_side_view(
        header_assemblies,
        rows=state.rows,
        coil_hand=state.coil_hand,
        airflow_arrow=airflow_arrow,
        return_connection_size=state.return_connection_size,
    )

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="{_esc(request.render_options.viewBox)}" role="img" aria-labelledby="phase2a-title phase2a-desc">
  <title id="phase2a-title">CoilForge Phase 2A DX Header 1 review aid</title>
  <desc id="phase2a-desc">EZ Coil style review-aid grid generated from the current DX Header 1 parameter state. OAL remains review required. { _esc(legacy_summary) }</desc>
  <defs>
    <marker id="arrowhead" markerWidth="12" markerHeight="8" refX="10" refY="4" orient="auto">
      <path d="M 0 0 L 12 4 L 0 8 z" class="arrow-fill"/>
    </marker>
    <style>
      .sheet {{ fill: #ffffff; stroke: #1f2937; stroke-width: 4; }}
      .grid-line {{ fill: none; stroke: #b8b8b8; stroke-width: 1; }}
      .thin-line {{ fill: none; stroke: #c6c6c6; stroke-width: 1; }}
      .view-geometry {{ fill: #fbfbfb; stroke: #bdbdbd; stroke-width: 2; }}
      .view-detail {{ fill: none; stroke: #cfcfcf; stroke-width: 2; }}
      .zone-label {{ fill: #111827; font: 700 15px Arial, sans-serif; letter-spacing: 0; }}
      .title-main {{ fill: #111827; font: 700 16px Arial, sans-serif; letter-spacing: 0; }}
      .title-sub {{ fill: #111827; font: 14px Arial, sans-serif; letter-spacing: 0; }}
      .sheet-text {{ fill: #1f2937; font: 16px Arial, sans-serif; letter-spacing: 0; }}
      .callout-text {{ fill: #111827; font: 800 20px Arial, sans-serif; letter-spacing: 0; }}
      .panel-text {{ fill: #172033; font: 700 18px Arial, sans-serif; letter-spacing: 0; }}
      .panel-small {{ fill: #334155; font: 13px Arial, sans-serif; letter-spacing: 0; }}
      .warning-small {{ fill: #92400e; font: 700 15px Arial, sans-serif; letter-spacing: 0; }}
      .blocked-small {{ fill: #991b1b; font: 700 15px Arial, sans-serif; letter-spacing: 0; }}
      .dimension-line {{ stroke: #242092; stroke-width: 1.2; fill: none; marker-end: url(#arrowhead); }}
      .dimension-label {{ fill: #0d0877; font: 700 23px Arial, sans-serif; letter-spacing: 0; }}
      .dimension-label-small {{ fill: #0d0877; font: 700 20px Arial, sans-serif; letter-spacing: 0; }}
      .connection-geometry {{ fill: #ffffff; stroke: #c4c4c4; stroke-width: 2; }}
      .header-face {{ fill: #fdfdfd; stroke: #bdbdbd; stroke-width: 2; }}
      .header-stub {{ stroke: #757575; stroke-width: 3; fill: none; }}
      .header-pipe {{ fill: #f8fafc; stroke: #4b5563; stroke-width: 2.5; }}
      .header-connection {{ fill: #ffffff; stroke: #4b5563; stroke-width: 1.8; }}
      .header-supply .header-pipe {{ stroke: #1d4ed8; }}
      .header-return .header-pipe {{ stroke: #7c2d12; }}
      .header-distributor .header-connection {{ fill: #dbeafe; stroke: #1d4ed8; }}
      .header-label-muted {{ fill: #475569; font: 700 13px Arial, sans-serif; letter-spacing: 0; }}
      .table-cell {{ fill: #ffffff; stroke: #b8b8b8; stroke-width: 1; }}
      .table-code {{ fill: #111827; font: 18px Arial, sans-serif; letter-spacing: 0; text-anchor: middle; }}
      .table-value {{ fill: #111827; font: 17px Arial, sans-serif; letter-spacing: 0; text-anchor: middle; }}
      .spec-cell {{ fill: #ffffff; stroke: #c4c4c4; stroke-width: 1; }}
      .spec-heading {{ fill: #111827; font: 18px Arial, sans-serif; letter-spacing: 0; }}
      .spec-line {{ fill: #111827; font: 14px Arial, sans-serif; letter-spacing: 0; }}
      .watermark {{ fill: #b91c1c; font: 800 22px Arial, sans-serif; letter-spacing: 0; }}
      .metadata {{ fill: #475569; font: 14px Arial, sans-serif; letter-spacing: 0; }}
      .blocked-banner {{ fill: #fee2e2; stroke: #b91c1c; stroke-width: 3; }}
      .blocked-banner-text {{ fill: #991b1b; font: 800 24px Arial, sans-serif; letter-spacing: 0; }}
      .arrow-fill {{ fill: #64748b; }}
    </style>
  </defs>
  <g id="zone.sheet_frame">
    <rect x="90" y="70" width="1410" height="1085" class="sheet"/>
    <line x1="1320" y1="70" x2="1320" y2="1005" class="grid-line"/>
    <line x1="90" y1="1005" x2="1500" y2="1005" class="grid-line"/>
  </g>
  <g id="zone.ez_top_callouts">
    {''.join(callout_text)}
    <text x="655" y="90" class="sheet-text">Coilmaster will revise any drawing that contains component interferences</text>
  </g>
  {status_banner}
  <g id="zone.front_view" data-grid-style="{_esc(grid["style_id"])}">
    <rect x="{casing_x}" y="{casing_y}" width="{casing_width}" height="{casing_height}" class="view-geometry"/>
    <rect x="{face_x}" y="{face_y}" width="{face_width}" height="{face_height}" class="view-detail"/>
    <path d="M {face_x - 10} {face_y - 96} H {face_x + face_width - 10}" class="dimension-line"/>
    <text id="label.FL.front" data-source-field="fin_length" x="{face_x + face_width / 2 - 35}" y="{face_y - 106}" class="dimension-label">{_esc(dimension_values["FL"])} FL</text>
    <path d="M {casing_x + 25} {casing_y + casing_height + 86} H {casing_x + casing_width - 4}" class="dimension-line"/>
    <text id="label.CL.front" data-source-field="casing_length" x="{casing_x + casing_width / 2 - 25}" y="{casing_y + casing_height + 112}" class="dimension-label">{_esc(dimension_values["CL"])} CL</text>
    <path d="M {face_x + face_width / 2} {face_y + face_height} V {face_y}" class="dimension-line"/>
    <text id="label.FH.front" data-source-field="fin_height" x="{face_x + face_width / 2 - 18}" y="{face_y + face_height / 2 + 2}" class="dimension-label">{_esc(dimension_values["FH"])} FH</text>
    <text id="label.CH.front" data-source-field="casing_height" x="{casing_x - 4}" y="{casing_y + casing_height / 2}" class="dimension-label">{_esc(dimension_values["CH"])} CH</text>
    <text id="label.TF.front" data-source-field="top_flange" x="{face_x + face_width - 120}" y="{face_y + 40}" class="dimension-label">{_esc(dimension_values["TF"])} TF</text>
    <text id="label.BF.front" data-source-field="bottom_flange" x="{face_x + 36}" y="{face_y + face_height - 16}" class="dimension-label">{_esc(dimension_values["BF"])} BF</text>
    <text id="label.RF.front" data-source-field="return_face" x="{casing_x + 46}" y="{casing_y + casing_height + 62}" class="dimension-label">{_esc(dimension_values["RF"])} RF</text>
    <text id="label.HF.front" data-source-field="header_face" x="{casing_x + casing_width - 130}" y="{casing_y + casing_height + 62}" class="dimension-label">{_esc(dimension_values["HF"])} HF</text>
    <text id="label.OAL.front" data-source-field="observed_oal" data-review-status="observed_candidate_review_required" x="{face_x + face_width / 2 - 20}" y="{face_y - 45}" class="dimension-label">{_esc(dimension_values["OAL"])} OAL</text>
    <text id="label.RB.front" data-source-field="return_bend_allowance" x="{casing_x - 30}" y="{face_y - 120}" class="dimension-label">{_esc(dimension_values["RB"])} RB</text>
    <polygon points="{face_x + 16},{face_y + face_height - 58} {face_x + 42},{face_y + face_height - 100} {face_x + 32},{face_y + face_height - 48}" fill="#a8a8a8"/>
    <polygon points="{face_x + face_width - 42},{face_y + 12} {face_x + face_width - 18},{face_y + 40} {face_x + face_width - 54},{face_y + 86}" fill="#a8a8a8"/>
  </g>
  <g id="zone.side_header_view" data-header-assembly-count="{len(header_assemblies)}" data-header-pair-count="{grid["header_pair_count"]}">
    <g id="zone.top_header_view">
      <text id="label.CD.side" data-source-field="casing_depth" x="610" y="322" class="dimension-label">{_esc(dimension_values["CD"])} CD</text>
      {header_top_view}
    </g>
    <g id="zone.connection_side_view">
      {header_side_view}
    </g>
  </g>
  <g id="zone.right_panel">
    <g id="zone.ez_right_spec_grid">
      {''.join(right_panel_text)}
    </g>
  </g>
  <g id="zone.bottom_dimension_table">
    <g id="zone.ez_bottom_grid">
      {''.join(dimension_cells)}
    </g>
  </g>
  <g id="zone.title_block">
    <rect x="100" y="1061" width="244" height="94" class="table-cell"/>
    <text x="125" y="1121" class="title-main">COILMASTER</text>
    <rect x="344" y="1061" width="252" height="94" class="table-cell"/>
    <text x="358" y="1080" class="panel-small">ALL DIMENSIONS ARE IN INCHES</text>
    <text x="358" y="1100" class="panel-small">STANDARD TOLERANCES APPLY</text>
    <rect x="596" y="1061" width="388" height="94" class="table-cell"/>
    <text x="610" y="1085" class="title-main">NOTES: {_esc(note_line)}</text>
    <rect x="984" y="1061" width="220" height="94" class="table-cell"/>
    <text x="995" y="1090" class="title-main">Tag: {_esc(title_cells["tag"])}</text>
    <rect x="1204" y="1061" width="296" height="94" class="table-cell"/>
    <text x="1215" y="1088" class="title-sub">WO # {_esc(title_cells["wo_number"])}</text>
    <text x="1355" y="1088" class="title-sub">Item: {_esc(title_cells["item"])} Rev: {_esc(title_cells["revision"])}</text>
    <text x="1215" y="1125" class="title-sub">Qty: {_esc(title_cells["quantity"])}</text>
    <text x="1325" y="1125" class="title-sub">{_esc(title_cells["created_by"])}</text>
    <text x="1235" y="1150" class="title-sub">{_esc(title_cells["model_number"])}</text>
    <text x="1165" y="1000" class="title-sub">Coil ID = {_esc(title_cells["coil_id"])}</text>
  </g>
  <g id="zone.review_metadata">
    <text x="105" y="230" class="watermark">{_esc(REVIEW_WATERMARK)}</text>
    <text x="105" y="250" class="metadata">template_id={_esc(TEMPLATE_ID)} | grid_style={_esc(grid["style_id"])} | john_review_required=true | export_allowed=false</text>
    {''.join(warning_text)}
    {''.join(blocked_text)}
  </g>
  <g id="markup.review"></g>
</svg>'''

    return SvgRenderResponse(
        svg=svg,
        metadata={
            "drawing_generation_run_id": f"draw_phase2a_{state.source_case_id.lower()}",
            "drawing_status": drawing_status,
            "release_status": DEFAULT_RELEASE_STATUS,
            "template_id": TEMPLATE_ID,
            "viewBox": request.render_options.viewBox,
            "source_case_id": state.source_case_id,
            "john_review_required": True,
            "grid_style_id": grid["style_id"],
            "grid_source_case_id": grid["source_case_id"],
            "grid_binding_count": len(grid["bindings"]),
            "grid_bindings": grid["bindings"],
            "header_assembly_count": len(header_assemblies),
            "header_pair_count": grid["header_pair_count"],
            "header_assemblies": header_assemblies,
            "oal_review_status": "observed_candidate_review_required",
        },
        warnings=list(dict.fromkeys(warnings)),
        blocked_fields=blocked_fields,
    )
