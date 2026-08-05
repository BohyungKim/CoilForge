# RP-001 — Add a TERRA V branch to the Coil Checklist HGRH sheet

**Status:** proposed · **Target:** Oxygen8's `Coil Checklist Template.xlsx`, not CoilForge
**Raised by:** KD-001 … KD-005 (`src/coilforge/rules/known_divergences.yaml`)
**Adjudicated:** 2026-08-04 · John

> **Nothing is applied by this document.** It targets a spreadsheet CoilForge does not
> own, and CoilForge's own `coil_header_rules.yaml` is not involved at all. Filed here
> rather than in the generated `outputs/rule_proposals/` because it is a deliverable to
> send onward, and a reference from a tracked registry must resolve for anyone who reads it.

---

## The defect

The checklist's HGRH sheet branches its dimension formulas on unit family and **has no
TERRA V arm**. A Terra V coil therefore falls through to the NOVA / VENTUM H else-branch,
and the sheet reports numbers computed from geometry that is not the coil's.

**Fingerprint:** `S = -conn_size`. A negative supply spacing is not a wrong Terra V value —
it is the else-branch arithmetic running on inputs it was never written for. Any cell whose
result carries that signature is downstream of the missing branch.

This is **structural, not a tolerance problem**. No magnitude of agreement would make the
else-branch right, which is why KD-001…005 carry no `delta_band` and are marked
unconditional rather than measured.

## Affected cells

Identified during the 2026-08-04 adjudication session against the live workbook:

| Cell | Dimension | Registry entry |
| --- | --- | --- |
| `HGRH!C27` | CD | KD-001 |
| `HGRH!C33` | S1 | KD-002 |
| `HGRH!C37` | S3 | KD-003 |
| `HGRH!C46` | O2 / O4 | KD-004, KD-005 |

⚠️ **Verify this cell list against the workbook before editing.** It was recorded from a
review session, not read out of a tracked file — the template is external and gitignored,
so nothing in this repository can confirm the addresses.

## Required change

Each cell needs a `TERRA V` arm ahead of the existing else-branch, resolving to the Terra V
values the EZ Coil SOP specifies:

- **CD** — the Terra V casing table, i.e. what R-074 keys as `TERRA_V|INTEGRATED|0xx`.
  Vertical units are substantially taller than Terra H and do not share its casing.
- **S1 / S3** — the Terra V `S = CD − Rn` branch. Note the boundary: `R2`/`R4` already
  AGREE between sheet and engine on the observed coil, which pins `len(return_spacing) == 2`
  and makes S3 a genuine SOP value rather than a fallback.
- **O2 / O4** — the Terra V I/O constant, not the Nova/Ventum derivation.

**The concrete formula text is deliberately not drafted here.** Writing it would mean
inventing the sheet's own conventions (its cell references, its unit-family test, its
lookup ranges) from outside the workbook. Whoever holds the file should mirror the shape of
the existing NOVA / VENTUM H arms and substitute the Terra V sources above.

## What is NOT proposed

- **`S5+`** — that was **our** defect, not the sheet's. CoilForge was falling through to the
  DX even-spacing safety net and printing distributor spacing on a reheat coil; fixed in
  `9abe5a7`, which blanks it instead. Do not add a sheet branch for a value we now decline
  to state.
- **`I3`** — likewise ours, and likewise fixed. R-046 explicitly declines to derive Supply
  2+ I/O, and CoilForge was asserting the Supply-1 constant across every odd header. It is
  deliberately absent from the registry: a repaired defect is not a known gap, and
  registering it would suppress the regression if it ever returned.

## Verification once applied

1. Re-fill the checklist for a Terra V HGRH coil (`2901 CAP1 Ball FAC` — `TV_B_072` +
   `RHHGRC-3` — is the same combination as the originally reported case).
2. The five KD rows should move from `mismatch` to `match`.
3. When they do, **withdraw KD-001…005 rather than leaving them**. A ruling that outlives
   its cause is the suppression-corruption failure mode the registry is built to avoid; an
   entry whose divergence no longer occurs is silently protecting nothing and will hide the
   regression if the branch is ever lost again.
