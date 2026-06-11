# CoilForge Project Instructions

## Project Identity

CoilForge is an internal coil engineering project. The long-term goal is a selection-software-like platform that helps engineering users move from captured coil inputs to checklist, drawing, JSON import/export payload, validation report, and markup-ready output.

## Immediate Purpose

The immediate Phase 1 purpose is a checklist-driven drawing populator for Direct Coil workflows using historical EZ Coil / CoilMaster JSON and PDF drawing data as reference data.

## Hard Boundaries

- Do not modify raw JSON files.
- Do not modify raw PDF files.
- Do not invent engineering values.
- Do not auto-approve generated drawings.
- Do not treat inferred mappings as confirmed without John or engineering review.
- Do not build the full selection calculation engine until explicitly approved.
- Do not initialize git, push, publish, or change external systems unless John explicitly asks.

## Preferred Workflow

1. Inspect the current project state and source files.
2. Extract evidence from JSON, PDFs, rendered drawings, and existing notes.
3. Normalize into explicit project fields.
4. Map source evidence to roadmap buckets and model fields.
5. Generate only the scoped artifact or document requested.
6. Validate with targeted file/count/schema checks.
7. Report facts, assumptions, risks, and next task clearly.

## Required Report-Back Format

- One-line result.
- Files changed.
- Validation performed.
- Remaining uncertainty.
- Next recommended task.

## Data Philosophy

- EZ Coil data is reference data, not automatically authoritative product logic.
- The checklist is the near-term user input layer.
- The Canonical Coil Model is the internal source of truth once defined.
- Drawing generation must be explainable, rule-driven, and reviewable.
- JSON import/export is a core architectural requirement, not an afterthought.
- Source evidence and normalized interpretation must remain separate when they differ.
- PDF extraction should evolve toward supplier-specific adapters selected from the PDF supplier/manufacturer context. Each supplier adapter must keep raw PDF data out of stored/exported payloads, preserve source evidence, and mark extracted mappings as review-required until John or engineering confirms them.

## Safety Rule

Generated drawings are engineering review aids until formally approved. They are not automatically released manufacturing drawings.
