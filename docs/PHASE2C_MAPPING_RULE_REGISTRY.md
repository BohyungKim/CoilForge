# Phase 2C.4 Mapping Rule Registry + Approval Status

## One-line implementation result

Phase 2C.4 adds a centralized, versioned mapping rule registry for the current sanitized DX/Header 1 path without treating any rule as final engineering approval.

## Files changed

- `src/coilforge/rules/__init__.py`
- `src/coilforge/rules/registry.py`
- `src/coilforge/rules/mapping_rules.py`
- `tests/test_phase2c_mapping_rule_registry.py`
- `docs/PHASE2C_MAPPING_RULE_REGISTRY.md`

## Rule model

Each registry rule contains:

- `rule_id`
- `rule_type`
- `source_system`
- `source_field`
- `canonical_path`
- `target_system`
- `target_field`
- `unit_policy`
- `conversion_policy`
- `confidence_policy`
- `review_policy`
- `approval_status`
- `approved_by`
- `notes`
- `fixture_refs`

## Rule types

Supported rule types:

- `submittal_to_canonical`
- `ez_to_canonical`
- `canonical_to_direct_coil`
- `direct_coil_to_drawing_intent`
- `canonical_to_drawing_intent`

## Approval status behavior

Supported approval statuses are `draft`, `review_required`, `approved`, `deprecated`, and `blocked`.

Current registry behavior:

- Current source and adapter rules are `review_required`.
- Canonical-to-DrawingIntent bridge rules are `draft`.
- `approved` rule count is `0`.
- Draft/review-required rules do not imply final approval.
- Unknown rule lookup returns a safe failure message instructing callers to treat the lookup as review-required or blocked.

## Initial coverage summary

The initial registry is generated from current code contracts:

- Sanitized submittal rules from `src/coilforge/submittal/rules.py`.
- Sanitized EZ JSON rules from `src/coilforge/adapters/ez_to_canonical.py`.
- Canonical-to-Direct Coil rules from `CANONICAL_DIRECT_COIL_FIELD_MAP`.
- DrawingIntent bridge rules for the fields consumed by `create_drawing_intent_from_direct_coil()`.

Current required Direct Coil fields all have a `canonical_to_direct_coil` rule. Fields with no source adapter coverage remain review-required through the canonical/direct layer instead of silently becoming ready.

## Unit policy

Unit handling is explicit:

- Unit-bearing rules use `source_unit_must_match_expected_unit:<unit>`.
- Unit-bearing rules use `blocked_without_explicit_conversion_rule`.
- Text or enum rules use `not_applicable_text_or_enum`.
- No unit conversion is approved in this phase.

## Known placeholders

- Material, casing, manufacturing option, and many optional performance fields have canonical-to-Direct Coil mapping rules but no approved source extraction rule.
- DrawingIntent bridge rules are draft/review-aid only.
- The registry does not implement selection calculations, derived drawing formulas, Direct Coil final export, or PDF export.
- `Header 1` remains the only supported header in the current Direct Coil field registry.

## John/engineering review items

- Review whether any `review_required` rule may be promoted to `approved`.
- Review Direct Coil drawing parameter semantics before any production-like drawing use.
- Confirm whether future source adapters need additional placeholder rules for unmapped source fields.
- Confirm any unit conversion rule before enabling conversion.

## Next recommended phase

Phase 2C.5 should use this registry as an input to a source reconciliation policy that preserves conflicts, source evidence, and review-required/blocked status without producing final export or quote-ready output.
