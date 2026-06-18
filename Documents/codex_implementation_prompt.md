# Codex Implementation Prompt — CoilForge Header Prepopulation Engine

Copy everything below this line into Codex.

---

You are implementing a **deterministic header prepopulation rule engine** for CoilForge, an internal HVAC coil ordering automation tool. The rules were extracted from two source-of-truth documents (Coil Checklist Template xlsx + EZ Coil Selection SOP Rev I) and are documented in `docs/rules/coil_header_rule_extraction.md`. That document is your ONLY source of rules. Read it fully before writing any code.

## Hard constraints (non-negotiable)

1. **No speculative rules.** Implement ONLY rules with a Rule ID in `docs/rules/coil_header_rule_extraction.md`. If a value seems "obvious" but has no Rule ID, do not implement it. Do not infer Terra behavior, do not fill gaps with HVAC domain knowledge.
2. **Evidence-backed only.** Every rule entry in the YAML must carry `evidence_refs` copied verbatim from the extraction doc (e.g., `["SOP §DX-TNVH", "CHK DX!C29"]`). A rule without evidence_refs must fail schema validation.
3. **Confidence/review gate is mandatory and enforced in code, not convention:**
   - `HIGH` → field appears in `response.values` (auto-prepopulate).
   - `MEDIUM` → field appears ONLY in `response.suggestions`, always with `review_required=true`. Never in `values`.
   - `LOW` and `CONFLICT` → field is never populated anywhere; it appears in `response.blocked` with `blocked_reason` citing both conflicting evidence refs.
   - Write a unit test that asserts no MEDIUM/LOW/CONFLICT rule can ever emit into `values` (iterate the whole rule table).
4. **Do not modify existing CoilForge export logic.** No changes to any export, Epicor, BOM, or quoting module. If the engine needs data from them, read through existing interfaces only. Zero diffs outside the files listed below plus their test files.
5. **Header prepopulation only.** No drawing generation, no fit-check enforcement beyond returning advisory flags, no EZ Coil automation, no persistence.
6. **Tests first.** Write `tests/test_header_prepopulate_engine.py` from the 20 golden cases (T01–T20) in §6 of the extraction doc BEFORE implementing the engine. All 20 must be encoded as failing tests first, then made green. Do not weaken a test to make it pass — if a golden case seems wrong, stop and flag it.

## Files to create (and only these)

- `src/coilforge/rules/coil_header_rules.yaml`
  One entry per Rule ID. Schema per entry:
  ```yaml
  - rule_id: R-005
    applies_to:
      coil_type: [DX, HGRH]
      product_family: ["*"]
      terra_variant: null        # or [TERRA_H, TERRA_H_C, TERRA_V]
      size_pattern: null         # or e.g. NOVA_1IN list
    field: return_bend
    value: 1.75                  # XOR formula
    formula: null                # e.g. "max(roundup(rows*0.866,0.125)+2, (circuits+1)*conn + (circuits-1)*1.5)"
    requires_inputs: []          # e.g. [rows, circuits, suction_conn_size]
    confidence: HIGH             # HIGH | MEDIUM | LOW | CONFLICT
    review_required: false
    blocked_reason: null
    evidence_refs: ["SOP §DX-TNVH", "SOP §DX-VP", "CHK DX!C29", "CHK HGRH!C32"]
  ```
- `src/coilforge/schemas/header_prepopulate.py`
  Pydantic v2 models:
  - `HeaderPrepopulateRequest`: `type_of_coil: CoilType`, `product_type: ProductFamily`, `unit_size: str`, plus OPTIONAL extended inputs exactly as listed in §4 of the extraction doc (`terra_variant`, `terra_ctrl_type`, `application`, `rows`, `feeds`, `qty_conn_per_header`, `circuits`, `suction_conn_size`, `conn_size`, `handing`, `coating`, `with_hgrh`, `hgrh_conn_size`, `hot_gas_bypass`, `installed_on_drain_pan`, `fh`, `fl`, `back_to_back`, `qty_valves`). All optional fields default to None.
  - `FieldResult`: `value`, `confidence`, `evidence_refs: list[str]`, `review_required: bool`, `review_required_reason: str | None`, `missing_inputs: list[str]`.
  - `HeaderPrepopulateResponse`: `values: dict[str, FieldResult]` (HIGH only), `suggestions: dict[str, FieldResult]` (MEDIUM only), `blocked: dict[str, FieldResult]` (LOW/CONFLICT, value=None, blocked_reason set), `missing_inputs: list[str]` (deduped union), `review_required: bool` (true if any suggestion/blocked present), `blocked_reason: str | None` (global, e.g. `unknown_unit_size`).
- `src/coilforge/services/header_prepopulate_engine.py`
  Pure function `prepopulate(request) -> HeaderPrepopulateResponse`. No I/O except loading the YAML once (module-level cache acceptable). Behavior:
  1. Validate `unit_size` against the per-product enumerations (Rule R-076). Unknown → global `blocked_reason="unknown_unit_size"`, no fields.
  2. Compute `size_class` for NOVA (R-075).
  3. `product_type == TERRA` and `terra_variant is None` → every Terra-variant-dependent rule resolves to review_required with reason `terra_variant_unresolved`; Terra-invariant HIGH constants (the list in extraction doc §7 item 3) still populate.
  4. Match rules by (coil_type, product_family, variant, size_pattern); evaluate `formula` rules only when all `requires_inputs` are present, else emit the field into `missing_inputs` reporting with empty value.
  5. Route results by confidence per constraint #3.
  6. Formula evaluation must be implemented with explicit safe functions (no `eval`): support `roundup(x, 0.125)` (round up to nearest eighth), `max`, arithmetic. The two CD tables (DX/HGRH 0.866-based, CWC/HWC 1.299-based) must reproduce the embedded SOP tables exactly for rows 1–12 — add a parametrized test asserting all 24 table values.
- `tests/test_header_prepopulate_engine.py` — golden cases T01–T20 plus: the confidence-gate invariant test, the CD-table reproduction test, a YAML schema validation test (every rule has rule_id, evidence_refs non-empty, confidence in enum), and a test that `prepopulate` never raises on any combination of valid enum inputs with all optional inputs None.
- `docs/rules/coil_header_rule_extraction.md` — copy in the provided extraction document unchanged.

## Specific behaviors to get right

- **Ventum+ DX distributor HD = 4.5 is HIGH** (both docs agree for Ventum+); the same field for NOVA/VENTUM H is CONFLICT R-030 (SOP says 0, checklist says 4.5). The rule table must encode this as two separate rules with different `applies_to`.
- **Single feed (`feeds == 1`)** flips CWC/HWC: SL → 12 (Nova/Ventum H) / 14 (Ventum+) as HIGH; I/O → "TBD" and HD → "N/A" as MEDIUM suggestions.
- **Notes are an ordered list**, base string first (R-007/R-008), conditional appends after. The coating appends (R-080/R-081) are CONFLICT — when `coating` is provided and != NONE, emit the notes field itself into `blocked` rather than choosing a wording.
- **Cross-coil rule R-051** (HGRH FH/FL must equal paired DX): implement as a validation flag only when both `fh`/`fl` and paired DX values are supplied; never as a value rule.
- Casing width/height lookup (R-074) ships as MEDIUM (single-source) with the Units-sheet data embedded in the YAML as a lookup table keyed by (product, application, unit_size).

## Definition of done

- All T01–T20 green; invariant tests green; `ruff` and `mypy --strict` clean on new files.
- `git diff --stat` shows changes ONLY in the five files above + test file.
- A short `IMPLEMENTATION_NOTES.md` is NOT required — any ambiguity you hit must instead be raised as a question, not resolved by guessing.
