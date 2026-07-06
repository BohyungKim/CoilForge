"""Constant-time project review gate — collapse per-coil review into an
exceptions-only rollup.

A coil needs John's eyes only when something about it is not ready. The gate checks,
per coil, three ready-conditions and surfaces ONLY the coils that fail one:

  1. **A shippable drawing exists** — we deliver CoilForge's OWN template drawing, so a
     coil with no generated drawing is a real exception (`_drawing_status`).
  2. **No blocked/undrawn value** — a dimension the engine could not derive is an
     exception (John must supply it).
  3. **engine <-> checklist agree** — the Oxygen8 Excel checklist recomputes dims
     independently (`checklist/compare.build_review`); a mismatch is an internal
     inconsistency -> a RED exception. (Optional — runs when the Excel cross-check is on.)

John 2026-07-05: CCSI's values are likely wrong and are NOT what we ship, so the CCSI
comparison is **off the primary path**. It remains available as an OPTIONAL overlay: when
``audit_reports`` are supplied, an engine<->CCSI mismatch is recorded as a documented
**override** (never gating; known classes like R return-spacing are pre-acknowledged).

All comparisons reuse ONE comparator (``checklist/compare._match``, tol 0.01). A coil
**auto-passes** when it has a drawing, no blocked value, and (if checked) agrees with the
checklist — so K (coils needing review) tracks the number of *problems*, not the number of
*coils*: a clean 50-coil project yields K=0. Pure; review aid only; never invents or approves.
"""

from __future__ import annotations

from typing import Any

from coilforge.checklist.compare import _match

# Drawing-param bases where an engine<->CCSI divergence is a KNOWN, accepted override
# (CoilForge's value is drawn, not CCSI's) — pre-acknowledged so it never inflates K.
# R = return-spacing family (R, R2, R3, ...); John 2026-07-04 chose CoilForge's values.
_ACKNOWLEDGED_OVERRIDE_BASES: frozenset[str] = frozenset({"R"})


def _base(key: str) -> str:
    """Drop a trailing header index: ``'R2' -> 'R'``, ``'HDx1' -> 'HDx'``, ``'HD' -> 'HD'``."""
    i = len(key)
    while i > 0 and key[i - 1].isdigit():
        i -= 1
    return key[:i] or key


def _checklist_by_tag(checklist_review: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    """{tag: {label: comparison}} from a ``build_review`` payload (engine vs checklist)."""
    out: dict[str, dict[str, Any]] = {}
    for sheet in (checklist_review or {}).get("sheets", []):
        out[sheet.get("tag")] = {
            c.get("label"): c for c in sheet.get("comparisons", [])
        }
    return out


def _audit_by_tag(audit_reports: list[dict[str, Any]] | None) -> dict[str, dict[str, Any]]:
    """{tag: {key: field}} from ``audit_export_result`` (engine vs CCSI-printed)."""
    out: dict[str, dict[str, Any]] = {}
    for report in audit_reports or []:
        out[report.get("tag")] = {
            f.get("key"): f for f in report.get("fields", [])
        }
    return out


def _drawing_status(workflow: dict[str, Any]) -> str | None:
    """None if the coil produced a shippable drawing; else a short reason it did not.

    John 2026-07-05: the drawing we deliver is CoilForge's OWN template drawing (CCSI's
    is discarded), so a coil with no drawing genuinely can't be shipped — it is a real
    per-coil exception the gate must surface.
    """
    td = workflow.get("template_drawing") or {}
    if td.get("svg"):
        return None
    if td.get("error"):
        return f"Drawing error: {td['error']}"
    if td.get("template_found") is False:
        return "No template bucket seeded for this coil (category / hand / header)."
    if td.get("generation_allowed") is False:
        return td.get("template_status") or "Drawing generation not allowed for this coil."
    return "Drawing not generated; review required."


def _classify_coil(
    page: dict[str, Any],
    checklist_comps: dict[str, Any] | None,
    audit_fields: dict[str, Any] | None,
) -> dict[str, Any]:
    """Classify one coil -> pass / exception / override, with the offending keys."""
    workflow = page.get("workflow") or {}
    params = (workflow.get("drawing_parameter_set") or {}).get("parameters") or {}

    exceptions: list[dict[str, Any]] = []
    overrides: list[dict[str, Any]] = []

    # 0. No shippable CoilForge drawing -> a real exception (we ship our own drawing).
    draw_reason = _drawing_status(workflow)
    if draw_reason:
        exceptions.append({"key": "DRAWING", "reason": "no_drawing", "detail": draw_reason})

    for key, param in params.items():
        value = param.get("value") if isinstance(param, dict) else None
        # 1. Blocked / not derived -> exception (John must supply or the engine can't).
        if value is None or value == "":
            exceptions.append({
                "key": key,
                "reason": "blocked",
                "detail": (param.get("blocked_reason") if isinstance(param, dict) else None)
                or "No value derived; review required.",
            })
            continue
        # 2. engine vs checklist MUST agree -> a mismatch is a real exception.
        cl = (checklist_comps or {}).get(key)
        if cl and cl.get("verdict") == "mismatch":
            exceptions.append({
                "key": key,
                "reason": "engine_vs_checklist",
                "engine": cl.get("coilforge"),
                "checklist": cl.get("checklist"),
            })
            continue
        # 3. engine vs CCSI -> documented override (never gating); ack known classes.
        au = (audit_fields or {}).get(key)
        if au and au.get("verdict") == "mismatch":
            overrides.append({
                "key": key,
                "engine": au.get("coilforge"),
                "ccsi": au.get("ccsi"),
                "acknowledged": _base(key) in _ACKNOWLEDGED_OVERRIDE_BASES,
            })

    verdict = "exception" if exceptions else ("override" if overrides else "pass")
    return {
        "tag": page.get("tag"),
        "verdict": verdict,
        "exceptions": exceptions,
        "overrides": overrides,
    }


def build_project_gate(
    workflow_result: dict[str, Any],
    *,
    checklist_review: dict[str, Any] | None = None,
    audit_reports: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Turn a ``run_pdf_to_drawing_workflow`` result into an exceptions-first rollup.

    ``checklist_review`` (``build_review`` output) and ``audit_reports``
    (``audit_export_result`` output) are optional extra sources — the gate uses
    whatever is present (engine always; more sources = stronger check), never
    fabricated. Returns per-coil verdicts + a summary whose ``exceptions_K`` is the
    number of coils that actually need John's eyes (independent of coil count on a
    clean project).
    """
    pages = (workflow_result or {}).get("pdf_coil_pages") or []
    checklist_by_tag = _checklist_by_tag(checklist_review)
    audit_by_tag = _audit_by_tag(audit_reports)

    coils: list[dict[str, Any]] = []
    for page in pages:
        tag = page.get("tag")
        coils.append(_classify_coil(page, checklist_by_tag.get(tag), audit_by_tag.get(tag)))

    exceptions_k = sum(1 for c in coils if c["verdict"] == "exception")
    override_coils = sum(1 for c in coils if c["verdict"] == "override")

    # Keys that are an exception on EVERY coil = a structural gap, surfaced once so it
    # reads as one finding rather than N (keeps the review pattern legible at scale).
    common_exception_keys: list[str] = []
    if coils:
        per_coil_keys = [{e["key"] for e in c["exceptions"]} for c in coils]
        common = set.intersection(*per_coil_keys) if per_coil_keys else set()
        common_exception_keys = sorted(common)

    return {
        "coils": coils,
        "summary": {
            "coils": len(coils),
            "exceptions_K": exceptions_k,
            "override_coils": override_coils,
            "common_exception_keys": common_exception_keys,
            "sources": {
                "engine": True,
                "checklist": bool(checklist_review),
                "ccsi": bool(audit_reports),
            },
        },
        "review_aid_only": True,
        "export_allowed": False,
        "production_drawing_approval_claimed": False,
    }
