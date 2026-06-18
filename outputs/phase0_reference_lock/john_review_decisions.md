# John Review Decisions

Run Timestamp: 2026-06-05T13:16:29-04:00

## Decisions Applied

### HGRH Classification Corrections

- EZC-0002 = HGRH / Header 1 / Single Feed / JOHN_CONFIRMED.
- EZC-0010 = HGRH / Header 1 / Single Feed / JOHN_CONFIRMED.
- EZC-0004 = HGRH / Header 1 / Single Feed / JOHN_CONFIRMED.
- EZC-0012 = HGRH / Header 1 / Non-Single Feed / JOHN_CONFIRMED.
- EZC-0008 = HGRH / Header 2 / Non-Single Feed / JOHN_CONFIRMED.

### DX HGBP / ASC Decision

- EZC-0013 ASC should be treated as HGBP by internal company standard.
- EZC-0013 is now DX / HGBP / JOHN_CONFIRMED with confidence HIGH_AFTER_JOHN_REVIEW.

## Data Model Correction

- coil_category identifies DX, HGRH, CWC, or HWC.
- header_type identifies Header 1, Header 2, Header 3, Header 4, or UNKNOWN.
- feed_type identifies Single Feed, Non-Single Feed, UNKNOWN, or NOT_APPLICABLE.
- special_feature identifies HGBP, ASC, None, or UNKNOWN.
- review_status identifies AI_INFERRED, JOHN_CONFIRMED, NEEDS_HUMAN_REVIEW, or INSUFFICIENT_DATA.

## Explicit Boundary

Single Feed is not Single Connection. HGRH Single Connection remains missing / uncertain.
