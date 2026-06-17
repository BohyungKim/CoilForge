# EZ Drawing Convention + Indexed Connection Data Model (Phase 3 design)

Status: **design, confirmed by John 2026-06-17.** No `src/` or test changes in this step.
Branch: `claude/phase2-drawing-engine` (worktree). Supersedes nothing; feeds Phases 3–5 of
the parametric drawing engine (CLAUDE.md "Drawing engine (parametric)").

## Why

Phase 1–2.7b built a DX **single-circuit** parametric engine: front view, header/side view,
LH↔RH mirror, EZ-aligned `{value} {CODE}` labels, and one collision-free, leader-connected
label pass. Phase 3 generalizes to **N indexed connections** and the full 17-template set.
This doc fixes (1) the EZ drawing convention to reproduce, (2) a normalized inches-only
**indexed** data model that extends the engine, (3) where the indexed data is sourced
upstream, (4) the coil-type → topology table, and (5) how this feeds the build phases.

### Spec source (confirmed)

The four named reference PDFs (`docs/reference/` — HHWC, CD-F-F, CDXC, CDM/RHHGRC) are **not
in the repo** (`*.pdf` is gitignored as customer data). The convention here is reconstructed
from the **committed redacted equivalents** — the `template.svg` files, which
`seed_evidence.json` confirms were seeded from those exact PDFs (e.g. `CDXC-1.PDF` →
`coilmaster_dx_lh_header1`) — plus the EZ renderer, the EZ-JSON loader, the rules, and docs.

- **[code]** = high-confidence, from the data path / renderer / rules.
- **[redacted-template]** = from the slot-substituted SVGs; validate against the real PDF at
  the phase that draws it (per decision C).

## 1. EZ drawing convention

### Three views
- **Front elevation** — outer casing `CL×CH`, inset finned face `FL×FH`, flange offsets
  `TF/BF/HF/RF`, return-bend `RB`, overall `OAL`.
- **Top / plan** — casing **depth `CD`**, header stems + stub lengths, and a labeled
  **AIRFLOW** arrow stored as an explicit direction (not derived from hand/category —
  `docs/DRAWING_TEMPLATE_SPEC.md`).
- **Side / end** — the header end: connection **ports as circles** at height offsets;
  headers / distributors; return **stub** `SL`.

### Per-feature representation
| Feature | How it's drawn | Driven by |
|---|---|---|
| **Port** [code] | small circle (connection/tube OD) at a height **offset**; `S/R` give spacing | `Headers[i].IO[0]` (`I`=supply, `O`=return), `Headers[i].SR` (`S`/`R`) |
| **Header** [code] | manifold with diameter label `HD{even}` | `Headers[return].HD` |
| **Distributor (DX)** [code + redacted-template] | `HDx{odd}` label + nozzle body + downward feeder extension | `IsDistributor`/`kind`; `HD`, `DistExtension`, model |
| **Stub** [code] | line from the header face outward, label `SL{id}` | `Headers[id].SL[0]` |
| **Airflow / depth** [code] | `AIRFLOW` arrow + `CD` dimension in the plan view | `airflow_direction`, `CD` |

### Indexed label convention [code, verified]
- Label **suffix = EZ header ID**. **Odd id = supply/distributor** (`I/S/HDx`); **even id =
  return** (`O/R/SL/HD`).
- `header_type N = N circuit-pairs`. Verified directly: the HGRH header-3 template carries
  `I1/I3/I5`, `O2/O4/O6`, `R2/R4/R6`, `HD2`, `SL2`.
- Visible text = EZ `"{value} {CODE}"` (value-first, no Ø/unit — adopted in Phase 2.6).
- Base (un-suffixed) dimension table (`ez_style_grid._dimension_table`):
  `ROWS X FH FL CH CL CD HD OAL SL I S O R TF BF HF RF RB`.

## 2. Indexed data model (inches only)

Replace the fixed `headers=(supply, return)` 2-tuple in
`src/coilforge/drawing/schematic_model.py` with an **indexed** structure. Front-view fields
(`CL/CH/FL/FH/TF/BF/HF/RF/CD/ROWS`) are unchanged.

```python
@dataclass(frozen=True)
class Connection:                  # a drawn port at the header end
    role: str                      # "I" | "O" | "S" | "R"  (offset I/O, spacing S/R)
    index: int                     # EZ suffix (1,2,3,4,5,6 …)
    value_in: float | None         # signed offset / spacing, inches (None -> omit+annotate)
    size_in: float | None          # connection/tube OD, inches (if known)

@dataclass(frozen=True)
class Header:                      # a header OR distributor manifold
    kind: str                      # "header" | "distributor"
    role: str                      # "supply" | "return"
    index: int                     # EZ id (odd supply, even return)
    diameter_in: float | None      # HD / HDx
    stub_len_in: float | None      # SL
    extension_in: float | None     # distributor DistExtension (DX)
    nozzle_spec: str | None        # DistributorModelNumber (DX)
    connection_size_in: float | None  # sweat connection OD (return)

# CoilGeometry gains:  header_end: tuple[Header, ...]  +  connections: tuple[Connection, ...]
#   ordered by index; circuits = max index // 2.
#   Back-compat: single-circuit side view reads index 1 (supply) / 2 (return);
#   Phase 3 iterates all indices.
```

`ViewLayout` already carries generic primitives (rects / circles / segments / labels /
dimensions), so the side view scales to N headers **without a layout-type change** — the
builder loops over `header_end`/`connections` by index, reusing the Phase 1.5 tiered
dimensioning and the Phase 2.7 unified de-collision. The single `mirror_view_x` is unchanged.
`None`/"REVIEW REQUIRED" → feature omitted + annotated (never invented).

## 3. Slot / data mapping (sourcing stays UPSTREAM in the loader)

Indexed slots already exist and are parsed in `src/coilforge/services/ez_json_drawing_loader.py`
[code]. The engine consumes only the gated `slot_values` via `_slot_inches`.

| Slot pattern | Geometry-schema source (`Headers[i]`) | PhysicalData NOTES token |
|---|---|---|
| `I{id}` / `O{id}` | `IO[0]` (supply / return) | `I1` / `O2` only |
| `S{id}` / `R{id}` | `SR` | `S1` / `R2` only |
| `HDx{id}` / `HD{id}` | `HD` (supply→HDx, return→HD) | `HD2` only |
| `SL{id}` | `SL[0]` | `SL1` / `SL2` only |
| `RETURN_CONN_SIZE` | `Headers[return].ConnectionSize[0]` (Phase 2.6) | pipeline `connectionSize` |

### Confirmed decisions
- **Multi-circuit = Geometry `Headers[]` only.** The loader already iterates `Headers[]` to
  emit `slot.I3/O4/R4/…`. The PhysicalData **NOTES** parser stays **single-circuit** (its 8
  tokens `{I1,S1,SL1,O2,R2,HD2,SL2,SupConnAngle}` are not extended). Multi-circuit is modeled
  strictly from the indexed Geometry slots.
- **Signed offsets = Geometry path only.** The Geometry numeric path and the model's
  `_slot_inches` (`-?\d…`) already accept negatives. The NOTES regex (`_TOKEN_RE`) stays
  **unsigned** — a documented limitation, not extended.

### Known gaps (to close at the phase that needs them)
- **Distributor extras unsourced.** `DistExtension`, `DistributorModelNumber`, `IsASC`/
  orientation are documented in `json_drawing_link_rules.yaml` but the loader does not emit
  them; per-header tube `Diameter` (e.g. 0.88") and the supply connection are absent (supply
  `ConnectionSize = 0`). → required for the **Phase 4** distributor drawing.
- **Multi-circuit / multi-feed PhysicalData** → "use the prepopulation engine" (no JSON
  indexed data). Out of the Phase 3 data path (per decision A).

## 4. Coil type → topology

18 active templates keyed `(category, hand, header_type)` (`template_population/catalog.py`);
`header_type 1/2/3 ≈ circuit count`. Topology from `coil_header_rules.yaml` +
`docs/REFERENCE_CASE_SET.md`.

| Category | Headers vs distributor | Circuits | Connection set | Ref EZC (drawing) |
|---|---|---|---|---|
| **DX** (header1/2/3) | **distributor** (`HDx`, supply) + return header (`HD`) | 1–3 | `I/S/HDx` + `O/R/SL/HD` per pair | EZC-0001 *CDXC-1*, -0011, -0007 |
| **DX HGBP** | distributor + hot-gas-bypass (ASC→HGBP) | 1 | DX + bypass | EZC-0013 |
| **HGRH** (header1/2/3) | **headers** (no distributor); feed_type ≠ header_type | 1–3 | `I/S` + `O/R/SL/HD`, conn_angle `LAS` | EZC-0002 *RHHGRC*, -0008, -0016 |
| **CWC** | header; vent/drain near MPT | 1 | 1 supply + 1 return | EZC-0014 *CCWC* |
| **HWC** | header | 1 | 1 supply + 1 return | EZC-0005 *HHWC* |

Named drawings: **CDXC**→DX, **RHHGRC/CDM**→HGRH multi-circuit, **CCWC/CD-F-F**→CWC,
**HHWC**→HWC.

## 5. Phase mapping (each phase has an EZ acceptance fixture)

- **Phase 3 — N indexed connections (side view).** Model: indexed `Header`/`Connection`
  lists; the side view loops indices, reusing the Phase 1.5 tiering + 2.7 de-collision +
  single mirror. **Acceptance:** HGRH header-3 (3 circuits, `I1/I3/I5…`) renders all
  ports/headers/stubs, no label overlaps, every label leader-connected, clean LH/RH. Fixture:
  a synthetic sanitized multi-circuit `Geometry.Headers[]`.
- **Phase 4 — distributor + feeder tubes + top/plan view.** Draw the distributor (nozzle +
  extension + feeder fan) and the top view (`CD` + airflow arrow). Requires the distributor
  extras sourced upstream first. **Acceptance:** DX (*CDXC*). Distributor visual fidelity
  (to-scale vs simplified symbol) to be confirmed against the redacted DX template when Phase
  4 is planned.
- **Phase 5 — type → topology spec table.** A `(category, hand, header, special)` table
  drives which features each of the 17 templates emits. **Acceptance:** one fixture per
  category (DX / HGRH / CWC / HWC + HGBP) renders the correct feature set; retire the static
  template dependency for covered categories.

## Constraints honored

Three-layer split kept; model in inches, datum/offset only; engine consumes gated slots only;
connection-size sourcing stays upstream in the loader; EZ representation borrowed but **not**
`phase2a/renderer.py`'s x18/x16 scaling; front-view fields untouched; one `mirror_view_x`.
