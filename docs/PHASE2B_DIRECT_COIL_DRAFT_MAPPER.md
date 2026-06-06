# Phase 2B Direct Coil Draft Mapper

Status: Phase 2B.5 model/mapper baseline.

Scope: review-only `DirectCoilInputDraft` model and canonical-to-Direct-Coil draft mapper. This phase does not implement final Direct Coil export, PDF export, UI, drawing generation, PDF parsing, OCR, or raw data changes.

## 1. Implementation Result

Phase 2B.5 adds a Direct Coil draft surface that contains every current Direct Coil registry field and maps values from `CanonicalCoilRecord` using the explicit canonical path map.

## 2. DirectCoilInputDraft Shape

`DirectCoilInputDraft` includes:

- `draft_id`
- `source_canonical_record_id`
- `groups`
- `fields`
- `summary`
- `export_status`

Each `DirectCoilDraftField` includes:

- `field_key`
- `label`
- `group`
- `value`
- `unit`
- `source_evidence`
- `mapping_rule`
- `status`
- `review_required`
- `blocked_reason`
- `manual_override`

`export_status` is `not_implemented`; no final export method is provided.

## 3. Mapping Behavior

The mapper uses `CANONICAL_DIRECT_COIL_FIELD_MAP` from the canonical validation layer. It iterates all fields in `DIRECT_COIL_FIELD_REGISTRY`, so the draft always exposes the full registry surface.

Mapped canonical values become draft fields with `mapping_rule = canonical:<path>`. Missing optional fields are `unmapped`. Missing required fields are `blocked`.

## 4. Field Status Behavior

Draft statuses are:

- `ready`
- `review_required`
- `blocked`
- `unmapped`
- `manual_override`

The draft summary counts each status across the full 52-field Direct Coil registry.

## 5. SourceEvidence Behavior

Mapped field evidence is copied from `FieldValue.source_evidence` into the corresponding `DirectCoilDraftField`. The mapper does not create raw source text or source documents.

## 6. Review-Required Policy

Inferred, ambiguous, missing, unreviewed, or explicitly review-required canonical values remain `review_required` in the Direct Coil draft. This includes supported but unreviewed `Header 1` values.

## 7. Blocked Policy

The mapper blocks:

- required fields missing from the canonical record,
- unsupported `header_type`,
- source-required mapped values without source evidence,
- unit mismatch when no explicit conversion rule exists.

Blocked draft fields are not exportable. Final Direct Coil export is out of scope.

## 8. Known Limitations

- No final Direct Coil export is implemented.
- No PDF export is implemented.
- No UI is added.
- No drawing generation changes are included.
- No PDF parser or OCR is implemented.
- Sanitized Phase 2B fixture does not yet provide required drawing parameters `CD`, `BF`, `TF`, and `CH`, so those correctly appear as blocked.
- Optional missing fields appear as `unmapped` until future canonical records provide values or approved defaults.

## 9. Next Phase

Recommended next phase: Phase 2B.6 Direct Coil readiness report packet.

Scope:

- Render a human-readable readiness report from `DirectCoilInputDraft`.
- List ready, review-required, blocked, and unmapped fields.
- Keep final export, UI, drawing generation, parser, OCR, and raw data out of scope.
