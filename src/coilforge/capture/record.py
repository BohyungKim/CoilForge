"""result dict -> ledger rows.

This module exists to ISOLATE one thing: reading the workflow result correctly.
Several obvious-looking keys do not hold what their names suggest, and reading
them would fill the corpus with plausible garbage — worse than no corpus, because
it would be trusted. Every trap is handled here and asserted in
tests/test_capture_ledger.py.

    page["coil_type"]      -> the cover row's ITEM TEXT, not the coil category
    page["product_type"]   -> the cover row's coil FAMILY, defaulting to "DX"
    result["drawing_parameter_set"] -> the SELECTED coil only, not each coil
    gate flags             -> absent when false; there is no default to read

The engine stage (values / suggestions / blocked + confidence) is deliberately
absent: HeaderPrepopulateResponse is lossily compressed into a review_items string
list inside derive_slot_values and discarded, so it cannot be recovered from the
result at all. Capturing it needs an engine hook (1c) — this module must not
pretend otherwise.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

from coilforge.capture import db
from coilforge.capture.schema import CAPTURE_SCHEMA_VERSION

# Gate flags live on template_drawing, and only when they fire — there is no
# false/default form to read. `.get(k) is not None` is the only correct test.
_GATE_FLAG_KEYS = (
    "not_registered_reason",
    "unregistered_product_line",
    "unregistered_ventum_plus_dx",
    "unsupported_hgbp_product_line",
    "hgbp_product_line_warning",
    "distributor_orientation_warning",
    "dedicated_family_template",
)


def _json(value: Any) -> str | None:
    if value is None:
        return None
    try:
        return json.dumps(value, ensure_ascii=False, default=str)
    except Exception:  # noqa: BLE001
        return json.dumps(str(value), ensure_ascii=False)


def _num(value: Any) -> float | None:
    """Numeric shadow of a value — makes aggregate queries cheap. Slot values mix
    floats and strings (slot.TAG, slot.HEADER_MATERIAL), so this is best-effort."""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


def _flag(value: Any) -> int | None:
    return None if value is None else int(bool(value))


class _CoilView:
    """One coil's captured surfaces, normalized across the three result shapes."""

    __slots__ = ("seq", "tag", "td", "params", "draft", "fit_inputs")

    def __init__(self, seq, tag, td, params, draft, fit_inputs):
        self.seq = seq
        self.tag = tag
        self.td = td or {}
        self.params = params or {}
        self.draft = draft or {}
        self.fit_inputs = fit_inputs or {}


def _tag_of(td: dict[str, Any]) -> str | None:
    extracted = td.get("extracted") or {}
    tag = extracted.get("tag")
    if tag:
        return str(tag)
    slot_tag = (td.get("slot_values") or {}).get("slot.TAG")
    return str(slot_tag) if slot_tag else None


def coil_views(result: dict[str, Any]) -> list[_CoilView]:
    """Normalize the three result shapes this codebase actually returns.

    1. PDF workflow  -> ``pdf_coil_pages[]``, N coils; each page's real values live
       under ``page["workflow"]``, NOT on the page itself.
    2. Text workflow -> one coil, ``template_drawing`` at the top level.
    3. /derive       -> one coil, and the result IS the template_drawing (it is
       ``pdf_text_to_template_drawing``'s return with extra keys bolted on).
    """
    pages = result.get("pdf_coil_pages")
    if isinstance(pages, list) and pages:
        views = []
        for index, page in enumerate(pages):
            if not isinstance(page, dict):
                continue
            workflow = page.get("workflow") or {}
            views.append(
                _CoilView(
                    index,
                    page.get("tag"),
                    workflow.get("template_drawing"),
                    # Per-coil. result["drawing_parameter_set"] is the SELECTED
                    # coil only -- using it would record 1 coil out of N.
                    workflow.get("drawing_parameter_set"),
                    workflow.get("direct_coil_input_draft"),
                    page.get("fit_inputs"),
                )
            )
        return views

    td = result.get("template_drawing")
    if isinstance(td, dict) and td:
        return [
            _CoilView(
                0,
                _tag_of(td),
                td,
                result.get("drawing_parameter_set"),
                result.get("direct_coil_input_draft"),
                None,
            )
        ]

    if "slot_values" in result or "extracted" in result:
        return [
            _CoilView(0, _tag_of(result), result, result.get("drawing_parameter_set"), None, None)
        ]

    return []


def _coil_row(run_id: str, coil_uid: str, view: _CoilView) -> tuple:
    from coilforge.submittal.coilmaster_drawing_extract import resolve_product_line

    td = view.td
    extracted = td.get("extracted") or {}

    # The picker label ("TERRA H" / "NOVA" / "VENTUM_PLUS"), NOT page["product_type"]
    # (which is the cover row's coil family and defaults to "DX").
    product_line = td.get("product_type") or None
    # terra_variant is never carried on the result; it is derivable purely from the
    # label, so recovering it here needs no engine change.
    _family, terra_variant = resolve_product_line(product_line)

    gate_flags = {key: td[key] for key in _GATE_FLAG_KEYS if td.get(key) is not None}

    return (
        coil_uid,
        run_id,
        view.seq,
        view.tag or _tag_of(td),
        # The engine coil token (DX/HGRH/CWC/HWC) -- page["coil_type"] is item text.
        extracted.get("coil_category"),
        product_line,
        terra_variant,
        td.get("unit_size"),
        extracted.get("hand"),
        extracted.get("header_type"),
        extracted.get("special_feature"),
        extracted.get("circuits"),
        td.get("template_id"),
        _flag(td.get("template_found")),
        _flag(td.get("generation_allowed")),
        td.get("drawing_value_source"),
        _flag(td.get("header_engine_used")),
        _json(gate_flags) if gate_flags else None,
    )


def _field_rows(run_id: str, coil_uid: str, view: _CoilView) -> list[tuple]:
    rows: list[tuple] = []

    # --- slot stage: what the drawing actually renders -----------------------
    slot_sources = view.td.get("slot_sources") or {}
    for key, value in (view.td.get("slot_values") or {}).items():
        source = slot_sources.get(key) or {}
        rows.append(
            (
                run_id, coil_uid, "slot", key, _json(value), _num(value), None,
                source.get("source"), source.get("validation"), None, None, None, None, None,
            )
        )

    # --- drawing_param stage: the review panel ------------------------------
    for key, param in (view.params.get("parameters") or {}).items():
        if not isinstance(param, dict):
            continue
        value = param.get("value")
        rows.append(
            (
                run_id, coil_uid, "drawing_param", key, _json(value), _num(value),
                param.get("unit"), None, None,
                # mode is the discriminating signal, not review_required (which is
                # hardcoded True on every branch of this path).
                param.get("mode"), param.get("status"),
                _flag(param.get("review_required")), param.get("blocked_reason"),
                _json(param.get("source_evidence")),
            )
        )

    # --- draft stage: the closest thing to canonical that reaches the result --
    # canonical_summary carries only 5 scalars (no FieldValues), so the honest
    # per-field surface with evidence is the Direct Coil draft. Named "draft"
    # rather than "canonical" so nobody later mistakes it for the record itself.
    for key, field in (view.draft.get("fields") or {}).items():
        if not isinstance(field, dict):
            continue
        value = field.get("value")
        rows.append(
            (
                run_id, coil_uid, "draft", key, _json(value), _num(value),
                field.get("unit"), field.get("mapping_rule"), None, None,
                field.get("status"), _flag(field.get("review_required")),
                field.get("blocked_reason"), _json(field.get("source_evidence")),
            )
        )

    return rows


def _artifact_rows(run_id: str, coil_uid: str, view: _CoilView) -> list[tuple]:
    # Three different SVGs exist per coil and they are different pictures. Only the
    # template drawing is the deliverable; the others are a static preview and the
    # parametric schematic. Gated coils carry "".
    svg = view.td.get("svg")
    if not svg:
        return []
    text = str(svg)
    return [(run_id, coil_uid, "template_svg", db.sha256_text(text), len(text), None, None)]


def _gate_rows(
    run_id: str,
    result: dict[str, Any],
    coil_uids: list[str],
    gate: dict[str, Any] | None = None,
) -> list[tuple]:
    """The triage label — "did John have to look at this coil".

    ``gate`` is the gate the ROUTE already computed, and it must win when given.
    build_project_gate is pure, but purity is not the same as taking the same
    arguments: /api/review/project passes ``checklist_review=`` so an engine-vs-Excel
    mismatch becomes an exception. Recomputing here without it would silently record
    those coils as "pass" — corrupting the exact label review triage trains on.
    Recomputing is only correct for milestones that never had a checklist to merge.

    It pairs with pdf_coil_pages by POSITION, so the index is a safe FK.
    """
    if not isinstance(result.get("pdf_coil_pages"), list) or not result["pdf_coil_pages"]:
        return []
    if gate is None:
        from coilforge.review.project_gate import build_project_gate

        gate = build_project_gate(result)
    rows = []
    for index, entry in enumerate(gate.get("coils") or []):
        if index >= len(coil_uids):
            break
        rows.append(
            (
                run_id, coil_uids[index], entry.get("verdict") or "",
                _json(entry.get("exceptions")), _json(entry.get("overrides")),
            )
        )
    return rows


def _input_rows(run_id: str, view: _CoilView) -> list[tuple]:
    """The engine input vector as ACTUALLY delivered — 10 fields, not 21.
    derive_slot_values passes an explicit subset, so application / header_count /
    qty_conn_per_header are structurally absent on the analyze path. NULL is the
    truth here, not a gap to fill in."""
    return [
        (run_id, view.seq, key, _json(value))
        for key, value in (view.fit_inputs or {}).items()
    ]


def _identity(result: dict[str, Any], payload: dict[str, Any]) -> tuple[Any, Any]:
    summary = result.get("pdf_intake_summary") or {}
    return (
        summary.get("project_number") or payload.get("project_number"),
        summary.get("project_name") or payload.get("project_name"),
    )


def _compare_rows(run_id: str, compare: dict[str, Any]) -> list[tuple]:
    """Weak-label rows for the review comparators. compare == {"comparator", "report"}.

    Two comparators with DIFFERENT verdict vocabularies — do not conflate:
      - mechanical_fit: verdict is NESTED (coils[i].width/height/drain_pan .verdict),
        one row per dimension, vocab PASS|FAIL|CANNOT_EVALUATE(+NOT_APPLICABLE). The
        coil tag IS present, so a row can join a coil later.
      - ccsi: verdict is FLAT (fields[j].verdict), one row per field, vocab
        match|mismatch|missing_one|both_missing. The body has NO coil identity, so
        coil_tag is NULL — an orphan row, recorded on purpose (1a'), never silently
        dropped. The count is surfaced so "0 rows" can't masquerade as "captured".

    columns: (run_id, coil_tag, comparator, key, slot, label, left_json, right_json, verdict)
    """
    comparator = (compare or {}).get("comparator")
    report = (compare or {}).get("report") or {}
    rows: list[tuple] = []

    if comparator == "mechanical_fit":
        for entry in report.get("coils") or []:
            if not isinstance(entry, dict):
                continue
            tag = entry.get("tag")
            for key in ("width", "height", "drain_pan"):
                check = entry.get(key)
                if not isinstance(check, dict) or not check.get("verdict"):
                    continue
                # label: width/height are a FitCheck (basis = FL/OAL/FH/CH); drain_pan
                # is a DrainPanFitResult with no basis, so label it by the paired coil.
                label = check.get("basis") if key != "drain_pan" else check.get("partner_tag")
                # available vs required lives entirely on the left side; there is no
                # right-hand comparand (it is a fit check, not a value diff).
                rows.append((
                    run_id, tag, "mechanical_fit", key, None,
                    label, _json(check), None, check["verdict"],
                ))
        return rows

    if comparator == "ccsi":
        for field in report.get("fields") or []:
            if not isinstance(field, dict) or not field.get("verdict"):
                continue
            rows.append((
                run_id, None, "ccsi", field.get("key"), None, None,
                _json(field.get("coilforge")), _json(field.get("ccsi")), field["verdict"],
            ))
        return rows

    if comparator == "checklist":
        # Engine vs the Coil Checklist's own Excel formulas — two independent
        # implementations of the same engineering, so a disagreement is a correctness
        # signal about CoilForge itself, not just about an external form. Unlike ccsi
        # these rows DO carry the coil tag (report.sheets[].tag), so they are
        # attributable at the (tag, project) identity grain and can be joined to a
        # later correction — that join is what makes "of the dims we flagged, how many
        # did John actually change?" answerable.
        #
        # "N/A" rows are dropped: mapping.py writes the literal string past the coil's
        # circuit count, and _match scores string-vs-number as a mismatch, so keeping
        # them would inflate the divergence rate with rows that have no dimension.
        from coilforge.services.drawing_param_resolver import param_key_for_slot

        for sheet in report.get("sheets") or []:
            if not isinstance(sheet, dict):
                continue
            tag = sheet.get("tag")
            for row in sheet.get("comparisons") or []:
                if not isinstance(row, dict) or not row.get("verdict"):
                    continue
                if str(row.get("coilforge") or "").strip().upper() == "N/A":
                    continue
                # `key` is the PANEL key, not the sheet's label. Corrections are filed
                # under the panel key (`_drawing_param_correction_rows`), and the sheet
                # calls the same dimension something else — its `S1` is the panel's `S`,
                # its `O4` is the panel's `O2`. Filed under the label, a flag would never
                # join the correction that followed it, and the override rate would read
                # zero for every per-header dim. The label is kept alongside for humans.
                rows.append((
                    run_id, tag, "checklist",
                    param_key_for_slot(row.get("slot")) or row.get("label"),
                    row.get("slot"), row.get("label"),
                    _json(row.get("coilforge")), _json(row.get("checklist")),
                    row["verdict"],
                ))
        return rows

    return rows


def _drawing_param_correction_rows(
    run_id: str, coil_uid: str, view: _CoilView, circuits: Any
) -> list[tuple]:
    """Drawing-param corrections (stage 'drawing_param'): one row per dimension a human
    overrode — the machine proposal (before) paired with the human override (after).

    PRIMARY (event-sourced, 1b reflection): when the derive stored
    ``view.td['manual_override_events']``, read the before-value + reason straight from
    that snapshot. Required once Tier-B reflection merges the override into ``slot_values``
    — a later override-free re-resolve would read the OVERRIDDEN slot and drop the
    correction. FALLBACK (recompute): older runs / Tier-A-only / analyze carry no snapshot;
    ``view.params`` is the panel WITH overrides (``mode == "manual"``) and the before is
    re-resolved WITHOUT overrides (deterministic — those paths never merged into slots).
    ``circuits`` MUST match the live derive so the baseline surfaces the same multi-header
    keys (I2/S2…). May raise — the caller wraps it.
    """
    # PRIMARY: event-sourced before-value + reason from the derive snapshot.
    events = view.td.get("manual_override_events") if isinstance(view.td, dict) else None
    if events:
        rows: list[tuple] = []
        for ev in events:
            if not isinstance(ev, dict):
                continue
            prev_value = ev.get("previous_value")
            new_value = ev.get("new_value")
            if prev_value == new_value:  # an override matching the machine value isn't one
                continue
            rows.append(
                (
                    run_id, coil_uid, ev.get("key"), "drawing_param",
                    _json(prev_value), _num(prev_value), ev.get("previous_mode"),
                    _json(new_value), _num(new_value), "manual",
                    ev.get("override_reason"),  # carried through 1b
                    _json(ev.get("source_evidence")),
                )
            )
        return rows

    # FALLBACK: recompute the pre-override baseline (no event snapshot present).
    panel = view.params.get("parameters") or {}
    overridden = {
        key: param
        for key, param in panel.items()
        if isinstance(param, dict) and param.get("mode") == "manual"
    }
    if not overridden:
        return []

    from coilforge.services.drawing_param_resolver import (
        parameter_set_from_template_drawing,
    )

    try:
        circuits_int = int(circuits) if circuits else None
    except (TypeError, ValueError):
        circuits_int = None
    baseline = parameter_set_from_template_drawing(view.td, circuits=circuits_int).parameters

    rows = []
    for key, param in overridden.items():
        new_value = param.get("value")
        base = baseline.get(key)
        prev_value = base.value if base is not None else None
        prev_mode = base.mode if base is not None else None
        if prev_value == new_value:
            continue
        rows.append(
            (
                run_id, coil_uid, key, "drawing_param",
                _json(prev_value), _num(prev_value), prev_mode,
                _json(new_value), _num(new_value), param.get("mode"),
                None,  # override_reason: not carried on the panel param dict
                _json(param.get("source_evidence")),
            )
        )
    return rows


def _spec_field_correction_rows(
    run_id: str, coil_uid: str, view: _CoilView
) -> list[tuple]:
    """Spec-field corrections (Phase 2, stage 'spec_field'): one row per spec input the
    engineer edited (circuits/rows/feeds/return_conn_size/coating). The before is the value
    on screen at correction time (event-sourced from ``view.td['spec_overrides']``, echoed
    by the derive from the validated request); no recompute, no slot mutation. May raise —
    the caller wraps it."""
    overrides = view.td.get("spec_overrides") if isinstance(view.td, dict) else None
    if not overrides:
        return []
    rows: list[tuple] = []
    for ov in overrides:
        if not isinstance(ov, dict):
            continue
        prev_value = ov.get("previous_value")
        new_value = ov.get("new_value")
        if prev_value == new_value:  # not a correction
            continue
        rows.append(
            (
                run_id, coil_uid, ov.get("field_key"), "spec_field",
                _json(prev_value), _num(prev_value), None,  # previous_mode: n/a for spec
                _json(new_value), _num(new_value), "manual",
                ov.get("override_reason"),
                None,  # evidence_json
            )
        )
    return rows


def _correction_rows(
    run_id: str, coil_uid: str, view: _CoilView, circuits: Any
) -> list[tuple]:
    """The correction half of the (input -> proposal -> correction) triple: drawing-param
    overrides (1b) + spec-field overrides (Phase 2), combined.

    NEVER propagates: anything here can raise, and this runs inside ``capture_milestone``'s
    single pre-transaction build, so an exception would sink the WHOLE milestone — including
    the "after" values already built for ``field_observation``. Any failure -> ``[]`` (a
    missing correction, never a lost run).
    """
    try:
        rows = _drawing_param_correction_rows(run_id, coil_uid, view, circuits)
        rows.extend(_spec_field_correction_rows(run_id, coil_uid, view))
        return rows
    except Exception as exc:  # noqa: BLE001 — a correction bug must not sink the run
        db.record_error(
            f"correction_rows:{run_id}", f"{type(exc).__name__}: {exc}", run_id=run_id
        )
        return []


def _rule_firing_rows(run_id: str, coil_uid: str, view: _CoilView) -> list[tuple]:
    """1c: per-field (rule_id, confidence) from the seam-A engine response the derive echoed
    onto the result under ``engine_provenance``. Empty unless it is present (only the
    Tier-A-fill derive attaches it — PDF-analyze discards its response in the frozen path)."""
    prov = view.td.get("engine_provenance") if isinstance(view.td, dict) else None
    if not prov:
        return []
    rows: list[tuple] = []
    for f in prov.get("firings") or []:
        if not isinstance(f, dict):
            continue
        rows.append(
            (
                run_id, coil_uid, f.get("field_key"), f.get("rule_id"),
                f.get("confidence"), _flag(f.get("review_required")), f.get("blocked_reason"),
            )
        )
    return rows


def _engine_call_rows(run_id: str, coil_uid: str, view: _CoilView) -> list[tuple]:
    """1c: one per-invocation count summary (values/suggestions/blocked). product_line /
    terra_variant / unit_size are NOT duplicated here — they join from the coil table."""
    prov = view.td.get("engine_provenance") if isinstance(view.td, dict) else None
    if not prov:
        return []
    call = prov.get("call") or {}
    return [
        (run_id, coil_uid, call.get("n_values"), call.get("n_suggestions"), call.get("n_blocked"))
    ]


def capture_milestone(
    milestone: str,
    *,
    result: dict[str, Any] | None = None,
    request_payload: dict[str, Any] | None = None,
    pdf_bytes: bytes | None = None,
    cover_page_hint: int | None = None,
    product: str | None = None,
    size: str | None = None,
    identity: str | None = None,
    gate: dict[str, Any] | None = None,
    compare: dict[str, Any] | None = None,
    journal_event_id: str | None = None,
    journal_error: str | None = None,
) -> str | None:
    """Persist one milestone's observations. Returns the run_id, or None when the
    ledger is off or the write failed.

    ``gate`` is the project gate the route already computed — pass it whenever the
    route has one, so the ledger records the verdict John was actually shown rather
    than a re-derivation that may have been given different inputs.

    ``compare`` == {"comparator", "report"} weak-labels from the review comparators
    (mechanical_fit / ccsi). These routes carry no workflow dict, so they produce a
    run with zero coils and only compare_observation rows.

    ``journal_event_id`` / ``journal_error`` are the outcome of the PO Release Case
    journal write (which runs first, since the ledger is append-only and cannot be
    back-patched): the event_id links this run to its JSONL line, and journal_error
    surfaces a journal failure that would otherwise be discarded.

    NEVER raises: every failure is logged to ``capture_error`` (or, if even that is
    impossible, to ``db.note_error``). Unlike the journal this does NOT require
    project identity — demo / sanitized / derive runs are ML data too, and dropping
    them is exactly the gap this ledger exists to close.
    """
    if not db.capture_enabled():
        return None

    run_id = uuid.uuid4().hex
    try:
        result = result if isinstance(result, dict) else {}
        payload = request_payload if isinstance(request_payload, dict) else {}
        views = coil_views(result)
        project_number, project_name = _identity(result, payload)
        summary = result.get("pdf_intake_summary") or {}

        run_row = (
            run_id,
            db.utc_now(),
            milestone,
            db.sha1_bytes(pdf_bytes) if pdf_bytes else None,
            cover_page_hint,
            product,
            size,
            summary.get("source_id"),
            # Filenames carry customer names -- hash, never store.
            db.sha256_text(str(summary.get("source_filename")))
            if summary.get("source_filename") else None,
            db.code_version(),
            db.rules_hash(),
            db.catalog_version(),
            CAPTURE_SCHEMA_VERSION,
            str(project_number) if project_number else None,
            str(project_name) if project_name else None,
            identity,
            journal_event_id,
            journal_error,
            len(views),
            1,
            None,
        )

        # Corrections (1b) are captured only on the manual-fill milestone, where the
        # panel already carries the human overrides (mode=="manual"). circuits comes
        # from the same source the live derive used (spec.get("circuits")).
        capture_corrections = milestone == "coil_manual_fill"
        circuits_hint = payload.get("circuits")

        coil_rows, field_rows, artifact_rows, input_rows = [], [], [], []
        correction_rows: list[tuple] = []
        rule_firing_rows: list[tuple] = []
        engine_call_rows: list[tuple] = []
        coil_uids: list[str] = []
        for view in views:
            coil_uid = uuid.uuid4().hex
            coil_uids.append(coil_uid)
            coil_rows.append(_coil_row(run_id, coil_uid, view))
            field_rows.extend(_field_rows(run_id, coil_uid, view))
            artifact_rows.extend(_artifact_rows(run_id, coil_uid, view))
            input_rows.extend(_input_rows(run_id, view))
            if capture_corrections:
                correction_rows.extend(
                    _correction_rows(run_id, coil_uid, view, circuits_hint)
                )
            # 1c engine provenance: presence-gated (only the Tier-A-fill derive attaches
            # engine_provenance), so no milestone check is needed — the builders return [].
            rule_firing_rows.extend(_rule_firing_rows(run_id, coil_uid, view))
            engine_call_rows.extend(_engine_call_rows(run_id, coil_uid, view))

        if pdf_bytes:
            artifact_rows.append(
                (run_id, None, "submittal_pdf", db.sha256_bytes(pdf_bytes),
                 len(pdf_bytes), summary.get("pdf_pages"), None)
            )

        gate_rows = _gate_rows(run_id, result, coil_uids, gate)
        compare_rows = _compare_rows(run_id, compare) if compare else []

        conn = db.connect()
        try:
            with conn:
                conn.execute(
                    "INSERT INTO run (run_id, ts_utc, milestone, input_hash, cover_page_hint,"
                    " product_line_hint, unit_size_hint, source_id, source_filename,"
                    " code_version, rules_hash, catalog_version, capture_schema_version,"
                    " project_number, project_name, request_identity, journal_event_id,"
                    " journal_error, coil_count, ok, error)"
                    " VALUES (" + ",".join("?" * 21) + ")",
                    run_row,
                )
                if coil_rows:
                    conn.executemany(
                        "INSERT INTO coil (coil_uid, run_id, coil_seq, tag, coil_category,"
                        " product_line, terra_variant, unit_size, hand, header_type,"
                        " special_feature, circuits, template_id, template_found,"
                        " generation_allowed, drawing_value_source, header_engine_used,"
                        " gate_flags_json) VALUES (" + ",".join("?" * 18) + ")",
                        coil_rows,
                    )
                if field_rows:
                    conn.executemany(
                        "INSERT INTO field_observation (run_id, coil_uid, stage, field_key,"
                        " value_json, value_num, unit, source, validation, mode, status,"
                        " review_required, blocked_reason, evidence_json)"
                        " VALUES (" + ",".join("?" * 14) + ")",
                        field_rows,
                    )
                if input_rows:
                    conn.executemany(
                        "INSERT OR REPLACE INTO run_input (run_id, coil_seq, key, value_json)"
                        " VALUES (?, ?, ?, ?)",
                        input_rows,
                    )
                if gate_rows:
                    conn.executemany(
                        "INSERT INTO gate_verdict (run_id, coil_uid, verdict, exceptions_json,"
                        " overrides_json) VALUES (?, ?, ?, ?, ?)",
                        gate_rows,
                    )
                if artifact_rows:
                    conn.executemany(
                        "INSERT INTO artifact (run_id, coil_uid, kind, sha256, byte_len,"
                        " page_count, filename_hash) VALUES (?, ?, ?, ?, ?, ?, ?)",
                        artifact_rows,
                    )
                if compare_rows:
                    conn.executemany(
                        "INSERT INTO compare_observation (run_id, coil_tag, comparator,"
                        " key, slot, label, left_json, right_json, verdict)"
                        " VALUES (" + ",".join("?" * 9) + ")",
                        compare_rows,
                    )
                if correction_rows:
                    conn.executemany(
                        "INSERT INTO correction (run_id, coil_uid, field_key, stage,"
                        " previous_value_json, previous_value_num, previous_mode,"
                        " new_value_json, new_value_num, new_mode, override_reason,"
                        " evidence_json) VALUES (" + ",".join("?" * 12) + ")",
                        correction_rows,
                    )
                if rule_firing_rows:
                    conn.executemany(
                        "INSERT INTO rule_firing (run_id, coil_uid, field_key, rule_id,"
                        " confidence, review_required, blocked_reason)"
                        " VALUES (" + ",".join("?" * 7) + ")",
                        rule_firing_rows,
                    )
                if engine_call_rows:
                    conn.executemany(
                        "INSERT INTO engine_call (run_id, coil_uid, n_values, n_suggestions,"
                        " n_blocked) VALUES (?, ?, ?, ?, ?)",
                        engine_call_rows,
                    )
        finally:
            conn.close()
        return run_id
    except Exception as exc:  # noqa: BLE001 — capture must never break a request
        db.record_error(
            f"capture_milestone:{milestone}", f"{type(exc).__name__}: {exc}", run_id=run_id
        )
        return None
