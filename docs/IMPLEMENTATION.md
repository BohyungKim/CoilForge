# CoilForge Implementation Architecture

## Intended Modules

1. Case Repository: Stores historical EZ Coil / CoilMaster case folders and generated reference artifacts without modifying raw files.
2. PDF Renderer / Extractor: Renders drawing pages and extracts searchable PDF text for evidence review.
3. JSON Parser: Reads JSON and JSON-like text payloads into structured source evidence.
4. Excel Checklist Parser: Future parser for checklist workbook inputs when checklist templates are introduced.
5. Submittal PDF Extractor: Future extractor that drafts checklist values from submittal PDFs with source citations.
6. Canonical Coil Model: Internal source-of-truth model that separates source fields, normalized fields, derived values, and review status.
7. Product / Coil-Type Rule Layer: Applies explicit DX, HGRH, CWC, and HWC rules without hiding engineering logic.
8. Drawing Populator: Maps checklist and canonical values into drawing labels and connection/header features.
9. SVG/PDF Drawing Exporter: Produces review-ready drawing artifacts for markup and validation.
10. Drawing Validation Engine: Checks generated labels, dimensions, and connection features against source evidence and mapping rules.
11. Markup / Review Layer: Captures engineer comments, questions, corrections, and approval state.
12. JSON Import / Export Adapter: Preserves JSON import/export as a first-class architecture requirement.
13. Future Selection Calculation Layer: Reserved for explicitly approved future rule/calculation work.

## Reference Data Flow

```text
Raw EZ Coil JSON/PDF
    -> Reference Case Parser
    -> Mapping Rules
    -> Canonical Coil Model
    -> Checklist Schema
    -> Drawing Populator
    -> Generated Drawing
    -> Validation Report
```

## Future User Workflow

```text
Submittal PDF Upload
    -> Auto Extract Checklist Draft
    -> Engineer Review / Edit Values
    -> Generate Drawing + Checklist Together
    -> Markup / Validation
    -> Export JSON / PDF
```

## Core Architecture Principles

- Raw EZ Coil JSON/PDF files are read-only reference inputs.
- Checklist values are near-term user inputs, not a substitute for the canonical model.
- The Canonical Coil Model should make value provenance explicit: source, normalized, derived, reviewed, or unknown.
- Drawing generation must remain rule-driven and inspectable.
- Validation reports should explain both matches and mismatches.
- Export payloads should preserve compatibility limits instead of silently fabricating missing engineering values.

## Immediate Implementation Direction

The next implementation pass should not build a populator yet. It should perform Phase 1A JSON-to-drawing dimension linkage analysis using the locked reference cases, then produce a reviewed mapping table for labels such as FH, FL, CH, CL, CD, HD, SL, I, S, O, R, TF, BF, HF, RF, and RB.
