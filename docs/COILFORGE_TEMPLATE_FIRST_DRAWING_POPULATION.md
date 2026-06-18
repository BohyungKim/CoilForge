# CoilForge Template-First Drawing Population

Status: Phase 2G implementation contract.

This pivots drawing generation from geometry reconstruction to supplier template slot population.
The renderer selects a supplier/coil/hand/header template, replaces stable `slot.*`
text anchors, and emits a review-aid SVG plus metadata. It does not approve drawings,
enable PDF export, or create production manufacturing output.

## Template Catalog

The v1 CoilMaster catalog has 22 buckets:

| Category | Buckets |
| --- | --- |
| DX | LH/RH x Header 1/2/3/4, plus LH/RH x HGBP |
| HGRH | LH/RH x Header 1/2/3/4 |
| CWC | LH/RH |
| HWC | LH/RH |

Template statuses:

- `active_review_aid`: generation is allowed as review-aid-only slot population.
- `seed_available`: a drawing pair exists but has not been promoted to active population.
- `needs_pair`: a real template drawing/source pair is still needed.
- `placeholder_blocked`: catalog bucket exists, but generation is blocked.

DX Header 4 and HGRH Header 3/4 remain `placeholder_blocked` until John provides
true reference drawings or explicitly approves a surrogate. CoilForge must not mirror
LH/RH templates automatically.

## Selector Contract

Selector input:

```json
{
  "supplier": "coilmaster",
  "coil_category": "DX",
  "coil_hand": "LH",
  "header_type": "Header 1",
  "special_feature": null,
  "source_case_id": "EZC-0001"
}
```

Selector output includes:

- `template_id`
- `template_status`
- `generation_allowed`
- `reasons`

The selector may return a matching bucket with `generation_allowed=false`; callers
must treat that as blocked and show the reason.

## Slot Binding Contract

Templates use stable SVG text ids such as:

- `slot.FH`, `slot.FL`, `slot.CH`, `slot.CL`, `slot.CD`
- `slot.HDx1`, `slot.HD2`, `slot.SL2`, `slot.I1`, `slot.S1`, `slot.O2`, `slot.R2`
- `slot.TAG`, `slot.MODEL_NUMBER`
- right-panel slots such as `slot.TUBE_MATERIAL`, `slot.CIRCUITING`, `slot.RETURN_CONN_SIZE`

Slot source precedence is:

1. reviewed canonical value
2. EZ JSON evidence
3. source PDF candidate
4. manual reviewed value
5. blocked or review-required

Missing required values render as `REVIEW REQUIRED` only for preview-allowed review
surfaces. If `preview_allowed=false`, missing required slots block population.

## First Active Seed

The first active template is `coilmaster_dx_lh_header1`, seeded from
`Case/#2/EZC-0001 - DX_1_LH`:

- EZ drawing PDF: `CDXC-1.PDF`
- EZ JSON export: `CDXC-1.txt`
- submittal PDF: present in the source folder, but the customer/source filename is
  not persisted in template artifacts
- rule observation: `outputs/drawing_rulebase_iterations/iteration_001_ezc0001_dx_header1`
- seed evidence record:
  `templates/drawing/coilmaster/dx/coilmaster_dx_lh_header1/seed_evidence.json`

Populated slots are limited to iteration-001 evidence. `OAL` remains
`observed_candidate_review_required` and is not an approved CoilForge formula.

## Safety Boundary

Generated drawings remain:

- `release_status=review_aid_only`
- `export_allowed=false`
- `production_approved=false`
- `pdf_export_enabled=false`

Raw PDFs and raw customer source files must not be copied into committed templates.
