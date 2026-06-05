# CoilForge Reference Case Set

## Status

Phase 0C locked reference set after John Engineering Review Decisions.

## Locked DX Cases

- EZC-0001: DX / Header 1 / AI_INFERRED.
- EZC-0003: DX / Header 1 / AI_INFERRED.
- EZC-0009: DX / Header 1 / AI_INFERRED.
- EZC-0011: DX / Header 2 / AI_INFERRED.
- EZC-0007: DX / Header 3 / AI_INFERRED.
- EZC-0013: DX / HGBP / JOHN_CONFIRMED. Source evidence is ASC; John confirmed ASC maps to HGBP by internal company standard.

## Locked HGRH Cases

- EZC-0002: HGRH / Header 1 / Single Feed / JOHN_CONFIRMED.
- EZC-0010: HGRH / Header 1 / Single Feed / JOHN_CONFIRMED.
- EZC-0004: HGRH / Header 1 / Single Feed / JOHN_CONFIRMED.
- EZC-0012: HGRH / Header 1 / Non-Single Feed / JOHN_CONFIRMED.
- EZC-0008: HGRH / Header 2 / Non-Single Feed / JOHN_CONFIRMED.

## Locked CWC Cases

- EZC-0014: CWC / Header 1 / AI_INFERRED.

## Locked HWC Cases

- EZC-0005: HWC / Header 1 / AI_INFERRED.
- EZC-0006: HWC / Header 1 / AI_INFERRED.
- EZC-0015: HWC / Header 1 / AI_INFERRED.

## Missing / Uncertain Buckets

- DX / Header 4.
- HGRH / Single Connection.
- HGRH / Header 3.
- HGRH / Header 4.

## Cases Requiring Future Data

- A true DX Header 4 reference case is required before that bucket can be implemented.
- A true HGRH Single Connection case is required; Single Feed must not be used as a substitute.
- HGRH Header 3 and Header 4 require future cases or additional John-confirmed examples.

## HGBP / ASC Handling

EZC-0013 contains ASC source evidence. John confirmed that ASC should be treated as HGBP by internal company standard for CoilForge. Future models should preserve both facts: `special_feature = HGBP` as normalized project classification and `source_feature = ASC` as source evidence.

## HGRH Header / Feed Type Separation

HGRH classification must separate `header_type` and `feed_type`. Single Feed is a feed type, not Single Connection. The corrected HGRH reference set uses John-confirmed classifications because the HGRH JSON schema does not expose Geometry.Headers.
