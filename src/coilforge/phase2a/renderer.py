from __future__ import annotations

import html
from typing import Any

from pydantic import BaseModel, Field

from coilforge.phase2a.models import DEFAULT_RELEASE_STATUS, DxHeader1ParameterState
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

    face_width = max(320, min(610, int(state.fin_length * 28)))
    face_height = max(220, min(410, int(state.fin_height * 24)))
    face_x = 105
    face_y = 275
    casing_width = max(face_width + 70, min(705, int(state.casing_length * 27)))
    casing_height = max(face_height + 55, min(485, int(state.casing_height * 23)))
    casing_x = face_x - 35
    casing_y = face_y - 25
    header_x = 820 if state.coil_hand.lower().startswith("left") else 1040
    airflow_arrow = "left to right" if state.airflow_direction == "left_to_right" else state.airflow_direction

    dimension_rows = _dimension_rows(state)
    dimension_cells = []
    for index, (label, value, source_field) in enumerate(dimension_rows):
        col = index % 6
        row = index // 6
        x = 95 + col * 175
        y = 815 + row * 58
        dimension_cells.append(
            f'<g id="label.{_esc(label)}.table" data-source-field="{_esc(source_field)}">'
            f'<rect x="{x}" y="{y - 30}" width="160" height="48" class="table-cell"/>'
            f'<text x="{x + 8}" y="{y - 10}" class="table-code">{_esc(label)}</text>'
            f'<text x="{x + 8}" y="{y + 10}" class="table-value">{_esc(value)}</text>'
            "</g>"
        )

    note_lines = state.notes[:4] or ["No review notes entered."]
    note_text = [
        _text_line(1240, 625 + idx * 28, f"- {note}", "panel-small")
        for idx, note in enumerate(note_lines)
    ]
    warning_text = [
        _text_line(1240, 815 + idx * 30, warning, "warning-small")
        for idx, warning in enumerate(warnings[:5])
    ]
    blocked_text = [
        _text_line(1240, 970 + idx * 28, field, "blocked-small")
        for idx, field in enumerate(blocked_fields[:6])
    ]
    status_banner = (
        '<g id="label.generation_blocked">'
        '<rect x="80" y="150" width="1420" height="52" class="blocked-banner"/>'
        '<text x="105" y="184" class="blocked-banner-text">GENERATION BLOCKED - REVIEW REQUIRED</text>'
        "</g>"
        if blocked
        else ""
    )

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="{_esc(request.render_options.viewBox)}" role="img" aria-labelledby="phase2a-title phase2a-desc">
  <title id="phase2a-title">CoilForge Phase 2A DX Header 1 review aid</title>
  <desc id="phase2a-desc">Local MVP SVG generated from the current DX Header 1 parameter state. OAL remains review required.</desc>
  <defs>
    <marker id="arrowhead" markerWidth="12" markerHeight="8" refX="10" refY="4" orient="auto">
      <path d="M 0 0 L 12 4 L 0 8 z" class="arrow-fill"/>
    </marker>
    <style>
      .sheet {{ fill: #ffffff; stroke: #1f2937; stroke-width: 4; }}
      .zone-label {{ fill: #475569; font: 700 18px Arial, sans-serif; letter-spacing: 0; }}
      .title-main {{ fill: #111827; font: 700 34px Arial, sans-serif; letter-spacing: 0; }}
      .title-sub {{ fill: #334155; font: 22px Arial, sans-serif; letter-spacing: 0; }}
      .sheet-text {{ fill: #1f2937; font: 20px Arial, sans-serif; letter-spacing: 0; }}
      .panel-text {{ fill: #172033; font: 700 18px Arial, sans-serif; letter-spacing: 0; }}
      .panel-small {{ fill: #334155; font: 16px Arial, sans-serif; letter-spacing: 0; }}
      .warning-small {{ fill: #92400e; font: 700 15px Arial, sans-serif; letter-spacing: 0; }}
      .blocked-small {{ fill: #991b1b; font: 700 15px Arial, sans-serif; letter-spacing: 0; }}
      .coil-geometry {{ fill: #f8fafc; stroke: #1f2937; stroke-width: 4; }}
      .fin-pack {{ fill: #e2e8f0; stroke: #475569; stroke-width: 2; }}
      .dimension-line {{ stroke: #2563eb; stroke-width: 3; fill: none; marker-end: url(#arrowhead); }}
      .dimension-label {{ fill: #1d4ed8; font: 700 20px Arial, sans-serif; letter-spacing: 0; }}
      .connection-geometry {{ fill: #dbeafe; stroke: #1e3a8a; stroke-width: 4; }}
      .table-cell {{ fill: #ffffff; stroke: #94a3b8; stroke-width: 2; }}
      .table-code {{ fill: #475569; font: 700 14px Arial, sans-serif; letter-spacing: 0; }}
      .table-value {{ fill: #111827; font: 700 16px Arial, sans-serif; letter-spacing: 0; }}
      .watermark {{ fill: #b91c1c; font: 800 32px Arial, sans-serif; letter-spacing: 0; }}
      .metadata {{ fill: #475569; font: 18px Arial, sans-serif; letter-spacing: 0; }}
      .blocked-banner {{ fill: #fee2e2; stroke: #b91c1c; stroke-width: 3; }}
      .blocked-banner-text {{ fill: #991b1b; font: 800 24px Arial, sans-serif; letter-spacing: 0; }}
      .arrow-fill {{ fill: #64748b; }}
    </style>
  </defs>
  <g id="zone.sheet_frame">
    <rect x="20" y="20" width="1560" height="1160" class="sheet"/>
  </g>
  <g id="zone.title_block">
    <text x="80" y="82" class="title-main">{_esc(state.coil_name)}</text>
    <text x="80" y="120" class="title-sub">{_esc(state.model_number)} | {_esc(state.coil_category)} | {_esc(state.header_type)} | Source {_esc(state.source_case_id)}</text>
    <text x="1120" y="82" class="sheet-text">release_status={_esc(DEFAULT_RELEASE_STATUS)}</text>
    <text x="1120" y="120" class="sheet-text">drawing_status={_esc(drawing_status)}</text>
  </g>
  {status_banner}
  <g id="zone.front_view">
    <text x="80" y="240" class="zone-label">Front view</text>
    <rect x="{casing_x}" y="{casing_y}" width="{casing_width}" height="{casing_height}" class="coil-geometry"/>
    <rect x="{face_x}" y="{face_y}" width="{face_width}" height="{face_height}" class="fin-pack"/>
    <path d="M {face_x - 18} {face_y + face_height + 48} H {face_x + face_width}" class="dimension-line"/>
    <text id="label.FL.front" data-source-field="fin_length" x="{face_x + 10}" y="{face_y + face_height + 82}" class="dimension-label">FL {_esc(_fmt(state.fin_length, " in"))}</text>
    <path d="M {face_x + face_width + 42} {face_y + face_height} V {face_y}" class="dimension-line"/>
    <text id="label.FH.front" data-source-field="fin_height" x="{face_x + face_width + 58}" y="{face_y + 44}" class="dimension-label">FH {_esc(_fmt(state.fin_height, " in"))}</text>
    <text id="label.CH.front" data-source-field="casing_height" x="{casing_x + 16}" y="{casing_y + 36}" class="dimension-label">CH {_esc(_fmt(state.casing_height, " in"))}</text>
    <text id="label.CL.front" data-source-field="casing_length" x="{casing_x + 16}" y="{casing_y + casing_height - 16}" class="dimension-label">CL {_esc(_fmt(state.casing_length, " in"))}</text>
    <text id="label.TF.front" data-source-field="top_flange" x="{face_x + 18}" y="{face_y - 44}" class="dimension-label">TF {_esc(_fmt(state.top_flange, " in"))}</text>
    <text id="label.BF.front" data-source-field="bottom_flange" x="{face_x + 18}" y="{face_y + face_height + 35}" class="dimension-label">BF {_esc(_fmt(state.bottom_flange, " in"))}</text>
    <path d="M {face_x + 40} {face_y + 82} H {face_x + min(face_width - 20, 330)}" class="dimension-line"/>
    <text id="label.airflow.front" data-source-field="airflow_direction" x="{face_x + 48}" y="{face_y + 68}" class="dimension-label">AIRFLOW {_esc(airflow_arrow)}</text>
  </g>
  <g id="zone.side_header_view">
    <text x="810" y="240" class="zone-label">Side / header view</text>
    <rect x="820" y="285" width="300" height="300" class="coil-geometry"/>
    <rect x="{header_x}" y="260" width="58" height="355" rx="10" class="connection-geometry"/>
    <circle cx="{header_x + 29}" cy="335" r="24" class="connection-geometry"/>
    <circle cx="{header_x + 29}" cy="510" r="24" class="connection-geometry"/>
    <text id="label.CD.side" data-source-field="casing_depth" x="845" y="625" class="dimension-label">CD {_esc(_fmt(state.casing_depth, " in"))}</text>
    <text id="label.return_connection_size.side" data-source-field="return_connection_size" x="845" y="660" class="dimension-label">RETURN {_esc(_fmt(state.return_connection_size, " in"))}</text>
    <text id="label.RB.side" data-source-field="return_bend_allowance" x="845" y="695" class="dimension-label">RB {_esc(_fmt(state.return_bend_allowance, " in"))}</text>
    <text id="label.coil_hand.side" data-source-field="coil_hand" x="845" y="730" class="dimension-label">HAND {_esc(state.coil_hand)}</text>
  </g>
  <g id="zone.right_panel">
    <rect x="1215" y="225" width="300" height="820" fill="#f8fafc" stroke="#475569" stroke-width="3"/>
    <text x="1240" y="270" class="zone-label">Review panel</text>
    <text id="label.rows.panel" data-source-field="rows" x="1240" y="315" class="panel-text">ROWS: {_esc(state.rows)}</text>
    <text id="label.fin_density_fpi.panel" data-source-field="fin_density_fpi" x="1240" y="348" class="panel-text">FPI: {_esc(_fmt(state.fin_density_fpi))}</text>
    <text id="label.circuiting_display.panel" data-source-field="circuiting_display" x="1240" y="381" class="panel-text">CIRCUITING:</text>
    <text x="1240" y="410" class="panel-small">{_esc(state.circuiting_display)}</text>
    <text x="1240" y="463" class="panel-text">OAL:</text>
    <text id="label.OAL.review_required" data-source-field="OAL" x="1240" y="492" class="blocked-small">REVIEW REQUIRED</text>
    <text x="1240" y="555" class="panel-text">Notes</text>
    {''.join(note_text)}
    <text x="1240" y="780" class="panel-text">Warnings</text>
    {''.join(warning_text) if warning_text else _text_line(1240, 815, "No warnings.", "panel-small")}
    <text x="1240" y="940" class="panel-text">Blocked fields</text>
    {''.join(blocked_text) if blocked_text else _text_line(1240, 970, "None", "panel-small")}
  </g>
  <g id="zone.bottom_dimension_table">
    <text x="80" y="770" class="zone-label">Bottom dimension table</text>
    {''.join(dimension_cells)}
  </g>
  <g id="zone.review_metadata">
    <text x="80" y="1065" class="watermark">{_esc(REVIEW_WATERMARK)}</text>
    <text x="80" y="1105" class="metadata">template_id={_esc(TEMPLATE_ID)} | viewBox={_esc(request.render_options.viewBox)} | john_review_required=true</text>
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
        },
        warnings=list(dict.fromkeys(warnings)),
        blocked_fields=blocked_fields,
    )
