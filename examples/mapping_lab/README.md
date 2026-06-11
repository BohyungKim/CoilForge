# CoilForge Mapping Lab Sample Dataset

Purpose: prepare sanitized examples that teach and validate how PDF-extracted coil data maps into engineer-filled Direct Coil fields.

This folder is intentionally review-only. Do not store raw PDFs, customer documents, private project data, credentials, or final export payloads here.

## Folder Shape

Each case uses the same structure:

```text
case_001_dx_hgrh/
  input/
    pdf_extracted.json
    source_images/
      README.md
  output/
    direct_coil_filled.json
  labels/
    field_links.csv
  notes.md
```

## Required Files

- `input/pdf_extracted.json`: sanitized structured data from the PDF extraction step. Keep section headings, page numbers, coil tags, coil sequence, field labels, values, units, and source evidence IDs.
- `output/direct_coil_filled.json`: sanitized engineer-filled Direct Coil values using stable internal field keys.
- `labels/field_links.csv`: the source-to-target training map. One row per Direct Coil target field.
- `input/source_images/`: optional screenshots of sanitized PDF sections. Use images only as source evidence, not as the primary machine-readable data.
- `notes.md`: reviewer context, assumptions, known defaults, and fields that need John or engineering review.

## Label CSV Columns

```csv
coil_tag,direct_field_key,direct_label,target_value,target_unit,source_section,source_label,source_value,source_unit,transform,source_type,confidence,review_note
```

Use these `source_type` values:

- `pdf`: value came directly from PDF-extracted data.
- `pdf_normalized`: value came from PDF but needed normalization, such as `LH -> Left`.
- `engineer_default`: value was entered by engineering even though the PDF did not provide it.
- `calculated`: value is calculated by Direct Coil or CoilForge, not copied directly.
- `review_required`: value needs John/engineering confirmation before it can become a rule.

Use these `confidence` values:

- `exact_match`
- `normalized_match`
- `engineer_default`
- `calculated`
- `needs_review`

## Recommended Workflow

1. Add or copy a case folder.
2. Fill `input/pdf_extracted.json` from sanitized PDF extraction output.
3. Fill `output/direct_coil_filled.json` from engineer-filled Direct Coil data.
4. Fill `labels/field_links.csv` to connect source fields to target fields.
5. Run the mapping lab dataset validation test.
6. Use mismatches to create deterministic mapping rules.

## Safety Rules

- Raw PDFs are not stored here.
- Raw customer/project names should be replaced with sanitized IDs.
- Mapping examples are not engineering approval.
- Every inferred/default/calculated field must remain review-required until confirmed.
