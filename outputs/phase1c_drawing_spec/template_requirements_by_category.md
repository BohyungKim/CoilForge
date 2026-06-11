# Phase 1C Template Requirements By Category

Status: Phase 1C draft for engineering review.

Created: 2026-06-05.

Scope: Category-specific drawing requirements for future review-ready SVG/PDF generation. This document does not generate drawings or approve manufacturing output.

## Evidence Baseline

Locked reference set:

| Category | Covered locked cases | Missing or uncertain buckets |
| --- | --- | --- |
| DX | EZC-0001, EZC-0003, EZC-0007, EZC-0009, EZC-0011, EZC-0013 | DX Header 4 missing. HGBP covered by EZC-0013, with source evidence `ASC` normalized to `HGBP` by John decision. |
| HGRH | EZC-0002, EZC-0004, EZC-0008, EZC-0010, EZC-0012 | HGRH Single Connection, Header 3, and Header 4 missing. |
| CWC | EZC-0014 | Only Header 1 covered. |
| HWC | EZC-0005, EZC-0006, EZC-0015 | Only Header 1 covered. |

Phase 1A dependency: no Phase 1A output files were present, so this file defines template needs rather than final source-field mappings.

## Common Requirements For All Categories

All category templates must support:

- Fixed sheet frame and title block.
- Top-left conditional callouts.
- Main front view.
- Top/header detail view.
- Side/connection view.
- Right-side specification panel.
- Bottom dimension table.
- Bottom notes block.
- `AIRFLOW` label and arrow.
- Review watermark: `REVIEW AID - NOT FOR MANUFACTURING`.
- Source/review metadata in the generated package.

Common labels:

- `FH`, `FL`, `CH`, `CL`, `CD`, `HD`, `OAL`, `SL`, `I`, `S`, `O`, `R`, `TF`, `BF`, `HF`, `RF`, `RB`
- Suffix variants including `HD1`, `HD2`, `HDx1`, `SL1`, `SL2`, `SL3`, `I1`, `I3`, `S1`, `S3`, `S5`, `O2`, `O4`, `O6`, `R2`, `R4`, `R6`
- `TUBE MATERIAL`, `FIN MATERIAL`, `CASING MATERIAL`, `COIL TUBE FACE`, `CIRCUITING`, `HEADER MATERIAL`, `FASTENER TYPE`, `DRY WEIGHT`, `INTERNAL VOLUME`
- `Coil ID`, `Tag`, `WO #`, `Qty`, `Item`, `Rev`, model number
- `NOTES:`

## DX Requirements

Reference cases:

- Header 1: EZC-0001, EZC-0003, EZC-0009
- Header 2: EZC-0011
- Header 3: EZC-0007
- HGBP: EZC-0013, source evidence `ASC`
- Header 4: missing

Template requirements:

- Support DX distributor/header top detail.
- Support `DISTRIBUTORS` right-panel block.
- Support `RETURN CONN SIZE` block.
- Support distributor extension callouts such as `DISTRIBUTOR 1 HAS 6" EXTENSION`.
- Support multiple distributor extension rows for Header 2/3 style drawings.
- Support circuiting display formats:
  - `2 Feed / 24 Pass`
  - `6 Feed / 12 Pass`
  - `4 Feed / 18 Pass`
  - `14 Passes per Feed`
  - `10 Passes per Feed`
  - `C1: ... Feed C2: ... Feed C3: ... Feed`
- Support HGBP/ASC source evidence display without collapsing the distinction.

DX review-required items:

- Whether DX drawings should display only return connection size or also supply/distributor connection size when canonical data has it.
- How to number distributor extension callouts relative to header/distributor geometry.
- Whether HGBP should have a visible label, remain in notes, or appear only in metadata.
- DX Header 4 cannot be generated from the current locked set.

## HGRH Requirements

Reference cases:

- Header 1, Single Feed: EZC-0002, EZC-0004, EZC-0010
- Header 1, Non-Single Feed: EZC-0012
- Header 2, Non-Single Feed: EZC-0008
- Single Connection: missing
- Header 3: missing
- Header 4: missing

Template requirements:

- Support supply and return connection blocks.
- Support `SUPPLY CONN SIZE` and `RETURN CONN SIZE`.
- Support HGRH side/header connection detail with `I`, `S`, `O`, `R`, `SL`, and `HD` suffix labels.
- Preserve `feed_type` separately from `header_type`.
- Support notes such as `Copper Straps Required. Add Headers & Stubouts...` when source-backed.
- Support `Do Not Coat Distributor Extensions` note when source-backed.
- Support circuiting display formats:
  - `1 Feed / 24 Pass`
  - `2 Feed / 14 Pass`
  - `3 Feed / 16 Pass`
  - `8 Passes per Feed`
  - `C1: ... Feed C2: ... Feed`

HGRH review-required items:

- Single Feed must not become Single Connection.
- HGRH header numbering in source JSON was not exposed in the HGRH schema and was corrected by John review. Generated drawings must preserve John-confirmed classification.
- HGRH Header 3 and Header 4 require future references or explicit John-approved rules.
- Stubout notes with embedded label/value pairs should not be auto-parsed into geometry until Phase 1A validates mapping.

## CWC Requirements

Reference cases:

- Header 1: EZC-0014

Template requirements:

- Support supply and return connection geometry.
- Support `SUPPLY CONN SIZE` and `RETURN CONN SIZE`.
- Support MPT connection text.
- Support vent/drain note:
  `Vent & Drain installed <= 3" from MPT connection.`
- Support single supply and single return note when source-backed.
- Support circuiting display formats:
  - `1 Feed/ 16 Pass`
  - `2 Feed/ 14 Pass`
- Support water-coil side view with visible connection stems and possible vent/drain symbols.

CWC review-required items:

- Only one CWC locked case exists, so layout generality is low-confidence.
- Vent/drain symbol placement must be visually reviewed.
- Any additional CWC header patterns need future reference data.

## HWC Requirements

Reference cases:

- Header 1: EZC-0005, EZC-0006, EZC-0015

Template requirements:

- Support supply and return connection geometry.
- Support `SUPPLY CONN SIZE` and `RETURN CONN SIZE`.
- Support MPT connection text.
- Support vent/drain note:
  `Vent & Drain installed <= 3" from MPT connection.`
- Support single supply and single return note when source-backed.
- Support circuiting display formats:
  - `1 Feed/ 14 Pass`
  - `1 Feed/ 12 Pass`
  - `1 Feed/ 26 Pass`
  - `1 Feed/ 24 Pass`
- Support PHWC/HHWC tags and model strings without turning them into separate categories unless John confirms that distinction.

HWC review-required items:

- Only Header 1 is covered.
- Water/glycol fluid details should be displayed from canonical/checklist data, not inferred from tag text.
- Small-coil layouts can create label crowding; MVP needs collision handling or explicit review warnings.

## MVP Template Recommendation

Build future templates in this order, after Phase 1 merged review approval:

1. DX Header 1 review template using EZC-0001 as the strongest DX Header 1 candidate.
2. HGRH Header 1 review template using John-confirmed HGRH cases.
3. HWC/CWC Header 1 water-coil template using EZC-0005 and EZC-0014.
4. DX Header 2/3 variants.
5. HGBP/ASC display support.

Do not start implementation until John approves the merged Phase 1 review packet.
