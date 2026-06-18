# EZ Drawing Convention + Indexed Connection Data Model (Phase 3 design)

Status: **design, confirmed by John 2026-06-17; extended for V3 (Phase 4-pre) 2026-06-17.**
No `src/` or test changes in this step. Branch: `claude/phase2-drawing-engine` (worktree).
Supersedes nothing; feeds Phases 3–5 of the parametric drawing engine (CLAUDE.md "Drawing
engine (parametric)"). The V3 distributor-strip design lives in **§6** (Phase 4).

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

> **Circuit positioning (verified, binding).** `S{odd}` / `R{even}` spacing positions each
> circuit along the depth `CD`; `I` (supply) / `O` (return) is a **per-row CONSTANT** offset
> from the edge — NOT what positions circuits. Every connection is dual-dimensioned (offset +
> spacing). This is the verified convention (EZC-0001/-0007); do not regress to any
> "stack circuits by the O offset" reading. [code: `schematic_layout.py:284`,
> `schematic_model.py:89-91`; verified real-PDF]

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
- **Distributor extras unsourced.** `DistExtension`, `DistributorModelNumber`, feeder OD, and
  `IsASC`/orientation are documented in `json_drawing_link_rules.yaml` but the loader does not
  emit them; the supply connection is correctly absent (supply `ConnectionSize = 0`). The
  sourcing decisions + proposed gated slots are settled in **§6** (Phase 4-pre); they are
  wired in Phase 4a. `ASCOrientation` stays **DEFERRED** (L-041, John 2026-06-11).
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
- **Phase 4 — distributor strip (V3 plan/top view).** Design settled in **§6**. Split:
  - **4-pre** (this) — convention extraction + data-sourcing design (DESIGN ONLY).
  - **4a** — loader/engine wiring: emit the new gated slots (`DistExtension{id}`,
    `DistModel{id}`, `DistOD{id}`, `AIRFLOW`) upstream; sanitized multi-circuit DX fixtures +
    loader/gate tests. No drawing code.
  - **4b** — the V3 plan/top strip drawing (coil body `FL×CD`, feeder fan, paired ports, stub
    pipes + caps, nozzle-detail glyph, DistExtension, AIRFLOW, re-introduced deferred labels).
    **Acceptance:** the real DX drawings — CDXC-1 single (EZC-0001), multi (EZC-0007) — human
    eyeball gate; clean LH/RH mirror; V1/V2 unchanged.
- **Phase 5 — type → topology spec table.** A `(category, hand, header, special)` table
  drives which features each of the 17 templates emits. **Acceptance:** one fixture per
  category (DX / HGRH / CWC / HWC + HGBP) renders the correct feature set; retire the static
  template dependency for covered categories.

## 6. V3 distributor strip (Phase 4 design)

Phase 3 shipped **V2** — the clean multi-circuit `S/R` spread (header end abstracted with `CD`
as an axis). **V3** is the distributor / header strip: the most visually detailed part of a DX
drawing, and the part that needs distributor data the loader does not yet emit. This section is
the Phase-4-pre design (confirmed by John 2026-06-17). DESIGN ONLY — no `src/` or test changes.

### 6.0 Confirmed decisions (this step)
- **V3 = a NEW plan/top view** (`FL × CD`, header end at right LH / left RH, AIRFLOW arrow).
  V2 stays the clean spread; V1 front untouched.
- **DistExtension source = rule-engine constant primary** (`dist_extension`, R-033 →
  `engine_slot_bridge` L-167); EZ-JSON `Headers[supply].DistExtension` (L-023) when a JSON is
  present; the `"DISTRIBUTOR N HAS X" EXTENSION"` callout is a **cross-check only**.
- **Tube/feeder OD = the distributor OD** from `distributors_display "OD:5/8"` (0.625") — the
  value on the DISTRIBUTORS data line; NOT `Headers[].Diameter` (0.88/0.625), NOT the coil
  tube `0.375`.

### 6.1 Convention extraction (verified against the real CDXC drawings)
Read for reference only from `Case/#3` EZC-0001 (single distributor) and EZC-0007 (3-circuit),
rendered to `build/ezref/ez0001_*.png` / `ez0007_*.png` (not committed).

**Three orthogonal views (one inches model, three backends):**
- **V1 front** = `CL × CH` (length × height). [code]
- **V2 spread/end** = `CD × CH` (depth × height) — the Phase 3 header-end abstraction. [code]
- **V3 plan/top** = `FL × CD` (length × depth), looking down. Shares `FL` with V1, `CD` with
  V2. Carries the distributor detail + AIRFLOW. [real-PDF EZC-0001/-0007]

**V3 distributor-strip elements** (`[real-PDF]` = seen on the drawing; validate to-scale vs
simplified-symbol fidelity at 4b against the real DX):

| Element | How it's drawn | Evidence |
|---|---|---|
| Feeder fan | `N` angled lines from one convergence point at the header face out to each supply circuit row | [real-PDF EZC-0007] (3 lines) |
| Per-circuit port pair | two small circles at the face per circuit (distributor→tube) | [real-PDF EZC-0001/-0007] |
| Stub pipe + end-cap | horizontal pipe of length `SL{id}` from the face, rectangular cap at its end | [real-PDF] |
| Nozzle-detail glyph | small symbol: body + feeder prongs (top) + extension stem (down), labeled `I` | [real-PDF EZC-0007] |
| DistExtension stub | the odd distributor's `6"` extension on the stem | [real-PDF callout + R-033] |
| Deferred labels | `HDx{odd}`/`HD{even}` Ø, `SL{id}`, `RETURN {conn}`, `DISTRIBUTORS (model) OD:x` | [real-PDF data table] |
| AIRFLOW arrow | filled arrow in plan view, direction from `airflow_direction` (stored, not derived) | [code + real-PDF] |

V3 reuses V2's `S/R` spacing + `I/O` offset positioning unchanged; it only ADDS the distributor
body, fan, extension, end-caps, AIRFLOW, and the labels V2 deferred.

### 6.2 Data-sourcing audit (the prerequisite)
**Already emitted by the loader [code]:** `I{id} O{id} S{id} R{id} HDx{id} HD{id} SL{id}`,
`RETURN_CONN_SIZE` (`ez_json_drawing_loader.py`; engine consumes via `_slot_inches`).

**Reality check.** The real DX cases (EZC-0001, EZC-0007) ship **no EZ `Geometry` JSON** —
only the PDF + extracted `.txt` + the sanitized fixture
`examples/sanitized/dx_header1_ezc0001_default.json`. So for DX the loader's `Headers[]` path
often does not fire; the **rule engine** (`coil_header_rules.yaml`) + display/callout strings
are the live source. Sourcing stays UPSTREAM; the engine never reads JSON.

| Datum | In the data as… | Link / engine | Emitted? |
|---|---|---|---|
| DistExtension (6") | `drawing_callouts` string + `Headers[].DistExtension` (L-023) + engine `dist_extension` (R-033, bridge L-167) | L-023 / R-033 | **No** |
| Distributor model | `distributors_display[0]` `"(1)501-2-3/16-1.5(0 ASC)"` ; `Headers[].DistributorModelNumber` (L-024) | L-024 | **No** |
| Feeder OD (5/8") | `distributors_display[1]` `"OD:5/8"` | (no link rule yet) | **No** |
| Supply connection | `Headers[supply].ConnectionSize = [0,0,0]` (distributor has none) | per EZ rule | n/a (correct) |
| AIRFLOW direction | `airflow_direction` (e.g. `"left_to_right"`) | stored field | confirm gated slot |
| ASC orientation | `Headers[0].ASCOrientation` | L-041 **DEFERRED** (2026-06-11) | stays deferred |

**Proposed NEW gated slots (wired UPSTREAM in 4a; engine consumes gated only):**
- `slot.DistExtension{id}` — engine `dist_extension` primary → `HIGH`; EZ-JSON override when
  present; callout = cross-check, never sole source.
- `slot.DistModel{id}` — `Headers[supply].DistributorModelNumber` / `distributors_display[0]`;
  **review_required** (engineering-unapproved string) → label-only, no geometry parsed from it.
- `slot.DistOD{id}` — `distributors_display "OD:x"` (0.625"); sizes the feeder/port circle + OD
  callout. **review_required** until John signs off the display-string mapping.
- `slot.AIRFLOW` — `airflow_direction` (explicit enum), `HIGH` (stored, never derived from
  hand/category).

Confidence gate unchanged: `HIGH→values`, `MEDIUM→suggestions(review)`, `LOW/CONFLICT→blocked`.

### 6.3 Model / layout / backend primitives (3-layer split preserved)
- **Model (inches only):** extend the indexed `Header` (§2) — `extension_in` (DistExtension),
  `nozzle_spec: str|None` (model), `feeder_od_in` (distributor OD). No pixels, no renderer types.
- **Layout (inches, datum/offset only):** add `layout_plan_top_view(geom)` beside the front/side
  builders, emitting only generic primitives (`Rect`/`Circle`/`Segment`/`Label`/`Dimension`) off
  computed datums. New `Segment.feature` kinds: `feeder_fan`, `nozzle_body`, `dist_extension`,
  `stub_cap`, `airflow_arrow`. Reuse `_spread_x`, tiered dimensioning, Phase-3c de-collision, the
  single `mirror_view_x`. No absolute coordinates; doubling `CD`/`FL` moves all dependents.
- **Backend (pixels only):** add CSS classes for the new feature kinds + an AIRFLOW arrow marker;
  geometry scales uniformly, annotation/arrow style fixed (annotation rule). New glyphs touch
  only `_SEGMENT_CLASS` + CSS. `build_dx_views` gains a `"plan"` entry beside `"front"`/`"side"`.

### 6.4 Phase-3-deferred labels — registered as V3 deliverables
Phase 3c deferred these to "the header strip (Phase 4)". Recorded here so nothing is permanently
dropped — re-introduced in the wider V3 strip (where they fit without raking the cramped V2
return column): `HDx{odd}`/`HD{even}` Ø callouts; `SL{id}` stub-length dim; `RETURN {conn}`
connection-size callout; `DISTRIBUTORS (model) OD:x` data line.

### 6.5 Open item for 4b
Distributor visual fidelity (to-scale fan/nozzle geometry vs a simplified symbol) is confirmed
against the real DX at 4b, per decision C.

## 7. Phase 5 — coil type → topology spec table

Status: **design, 2026-06-17.** No `src/` or test changes in this step. Branch:
`claude/phase5-topology` (new worktree off `main`). Extends §4 (type→topology) and §5
(phase map) into an executable spec table. DESIGN ONLY.

### 7.0 Confirmed decisions (this step)
- **One table, rules-as-data.** A `(category, header_type, special)` → feature-set table
  in YAML (house style: `schema_version`, per-row `id` + `evidence_refs`) is the single
  source of truth for which features each template emits. The engine reads the table; it
  does not hardcode per-category branches in Python.
- **Hand-invariant.** Rows carry **no `hand`** — LH/RH share a feature set; `mirror_view_x`
  reflects. Every row is validated LH **and** RH (mirror-covariance tests).
- **Reuse first.** DX (V1 front / V2 spread / V3 plan) primitives are reused unchanged.
  The only structural toggle is **supply kind**: `distributor` (DX) vs `plain_header`
  (HGRH/CWC/HWC). New glyphs are added only where a category genuinely needs one.
- **Gated-slots-only, fail-closed.** The engine consumes gated `slot_values` only; sourcing
  of every new datum stays UPSTREAM (5a). `None` / "REVIEW REQUIRED" → feature omitted +
  annotated, never invented. Confidence gate unchanged
  (`HIGH→values`, `MEDIUM→suggestions(review)`, `LOW/CONFLICT→blocked`).

### 7.1 The topology table (rules-as-data)
Proposed file: `src/coilforge/rules/drawing_topology_rules.yaml`. Shape:

```yaml
schema_version: "drawing-topology.v1"
# (category, header_type, special) -> feature set emitted. Hand-invariant (LH/RH via
# mirror_view_x). Engine consumes gated slots only; None/REVIEW -> omit+annotate.
topologies:
  - id: T-DX
    category: DX
    header_type: ["Header 1", "Header 2", "Header 3"]
    special: null
    circuits_from: header_type        # 1 / 2 / 3
    supply: distributor               # nozzle_body + feeder_fan + dist_extension
    return: header                    # connection_return + stub + stub_cap + HD
    views: [front, side, plan]
    features: [casing, finned, row, tube_run, nozzle_body, feeder_fan,
               dist_extension, connection_return, stub, stub_cap, airflow]
    labels:  [hdx, hd, sl, dist_data, return_conn]
    dims:    [CL, CH, FL, FH, TF, BF, HF, RF, CD, S, R, I, O, SL]
    new_primitives: []
    ref_ezc: [EZC-0001, EZC-0007, EZC-0011]
    status: implemented               # Phase 1-4

  - id: T-DX-HGBP
    category: DX
    header_type: null                 # catalog: dx_{lh,rh}_hgbp, single circuit
    special: HGBP
    circuits_from: const_1
    supply: distributor
    return: header
    extra: [hot_gas_bypass]           # asc=selected (R-083 HIGH when hot_gas_bypass);
                                       # asc_orientation BLOCKED (R-084 CONFLICT) -> omit+annotate
    views: [front, side, plan]
    features: [<T-DX features>, hgbp_bypass]
    new_primitives: [hgbp_bypass]
    ref_ezc: [EZC-0013]
    status: phase5b

  - id: T-HGRH
    category: HGRH
    header_type: ["Header 1", "Header 2", "Header 3"]
    special: null
    circuits_from: header_type
    supply: plain_header              # NO distributor: supply header port + manifold
    return: header
    extra: [conn_angle]               # LAS (R-047 HIGH)
    views: [front, side, plan]
    features: [casing, finned, row, tube_run, supply_header_port,
               connection_return, stub, stub_cap, conn_angle_glyph]
    labels:  [hd, sl, return_conn, conn_angle]
    dims:    [CL, CH, FL, FH, TF, BF, HF, RF, CD, S, R, I, O, SL]
    new_primitives: [supply_header_port, conn_angle_glyph]
    ref_ezc: [EZC-0002, EZC-0008, EZC-0016]
    status: phase5b

  - id: T-CWC
    category: CWC
    header_type: ["Header 1"]
    special: null
    circuits_from: const_1
    supply: plain_header
    return: header
    extra: [vent_drain]               # R-066 MEDIUM(review); Terra V R-067 LOW -> blocked
    views: [front, side, plan]
    features: [casing, finned, supply_header_port, connection_return,
               stub, stub_cap, vent_port, drain_port]
    labels:  [hd, sl, return_conn, vent_drain]
    dims:    [CL, CH, FL, FH, TF, BF, HF, RF, CD, I, O, SL]
    new_primitives: [supply_header_port, vent_port, drain_port]
    ref_ezc: [EZC-0014]
    status: phase5b

  - id: T-HWC
    category: HWC
    header_type: ["Header 1"]
    special: null
    circuits_from: const_1
    supply: plain_header
    return: header
    extra: [vent_drain]
    views: [front, side, plan]
    features: [<same set as T-CWC>]
    new_primitives: [supply_header_port, vent_port, drain_port]   # shared with CWC
    ref_ezc: [EZC-0005]
    status: phase5b
```

Notes: `circuits = max header index // 2` as today; `circuits_from: header_type` reads
1/2/3 from the catalog header type, `const_1` for single-circuit categories. `features` is
the union the composition layer emits; a feature whose slot is missing is omitted +
annotated (not an error).

### 7.2 Per-category convention extraction
`[code]` = data path / catalog / rules; `[redacted-template]` = the seeded SVGs; validate
real-PDF at 5b (decision C).

| Category | Views | Supply | Return | Category feature | Labels | Ref EZC |
|---|---|---|---|---|---|---|
| **DX** | V1/V2/V3 | distributor (`HDx`, nozzle+fan+ext) | header `HD`+`SL` | AIRFLOW, DistExtension | `HDx/HD/SL/dist_data/RETURN` | 0001/0007/0011 |
| **DX-HGBP** | V1/V2/V3 | distributor | header | **hot-gas-bypass / ASC** (orientation blocked) | DX + bypass callout | 0013 |
| **HGRH** | V1/V2/V3 | **plain header** (`I/S`, no distributor) | header `O/R/SL/HD` | **conn_angle `LAS`** | `HD/SL/RETURN/conn_angle` | 0002/0008/0016 |
| **CWC** | V1/V2/V3 | plain header (1) | header (1) | **vent/drain near MPT** | `HD/SL/RETURN/vent_drain` | 0014 |
| **HWC** | V1/V2/V3 | plain header (1) | header (1) | vent/drain | as CWC | 0005 |

The load-bearing difference is **DX draws the supply as a distributor** (nozzle body +
feeder fan + downward extension), while **HGRH/CWC/HWC draw the supply as a plain header
port** — same `I/S` offset+spacing positioning, no funnel/fan/extension. DX-HGBP is DX +
a bypass connection. CWC and HWC are the same drawing family (plain headers + vent/drain);
they differ in engineering meaning, not topology.

### 7.3 New primitives required (everything else is reused)
Reused unchanged: `casing`/`finned` rects, `connection_return` circle, `row`, `tube_run`,
`stub`, `stub_cap` segments, AIRFLOW arrow, `tier_pos`/`place_dimensions`/`decollide`/
`mirror_view_x`, all dimension/label machinery, the SVG backend frame.

| New primitive | Categories | Layer-2 feature kind | Layer-3 (CSS class) | Notes |
|---|---|---|---|---|
| **supply_header_port** | HGRH, CWC, HWC | `supply_header_port` (Circle + short manifold Segment) | `.header-port` | plain supply: reuses `connection_return` geometry pattern, supply side; replaces nozzle/fan/ext |
| **conn_angle_glyph** | HGRH | `conn_angle` (angled Segment + Label `LAS`) | `.conn-angle` | the LAS angled supply connection; label-only value if geometry unknown |
| **vent_port** / **drain_port** | CWC, HWC | `vent_port` / `drain_port` (small Circle/Segment near MPT) | `.vent` / `.drain` | label-only when position unsourced → omit+annotate |
| **hgbp_bypass** | DX-HGBP | `hgbp_bypass` (Segment path/glyph for ASC) | `.hgbp` | ASC connection; **asc_orientation omitted+annotated** (R-084 CONFLICT) |

Each new kind is a 3-layer-clean addition: a `Header`/geometry field (inches) if it carries
a dimension, a layout builder branch emitting generic primitives off datums, and one CSS
class + (annotation-fixed) glyph in the SVG backend's `_SEGMENT_CLASS`/`_CIRCLE_CLASS`. No
absolute coordinates; mirror-covariant placement.

### 7.4 Data-sourcing audit (mirrors §6.2 — sourcing stays UPSTREAM, fail-closed)
Already emitted by the loader/engine [code]: `I{id} O{id} S{id} R{id} HDx{id} HD{id}
SL{id} RETURN_CONN_SIZE`, plus Phase-4a `AIRFLOW`, `DistExtension{id}`, `DistModel{id}`,
`DistOD{id}`.

| Category | Datum | In the data as… | Engine rule | Emitted today? | 5a action |
|---|---|---|---|---|---|
| **HGRH** | conn_angle | `SupConnAngle` notes token (single-feed); engine `conn_angle` | **R-047 HIGH** `"LAS"` | token only, no slot | NEW `slot.conn_angle` ← engine R-047 primary, JSON token cross-check → **HIGH** |
| **HGRH** | supply/return position (multi) | indexed `Headers[]` `I/S/O/R` | R-048 MEDIUM (formula) | indexed slots exist | reuse existing `I{id}/S{id}/O{id}/R{id}` |
| **CWC/HWC** | vent_drain | (none in geometry/notes) | **R-066 MEDIUM(review)**; **R-067 LOW** (Terra V) → blocked | **none** | NEW `slot.vent_drain` ← engine R-066 → **MEDIUM/review**; Terra V → **blocked**; position unknown → omit+annotate |
| **DX-HGBP** | asc | `Headers[].IsASC` (L-040 STRONG) | **R-083 HIGH** `"selected"` (only_when hot_gas_bypass) | partial (`slot.ASC` from geometry) | NEW `slot.HGBP` ← engine R-083 bridge → **HIGH**; geometry override when present |
| **DX-HGBP** | asc_orientation | `Headers[].ASCOrientation` | **R-084 CONFLICT** | deferred (L-041) | stays **DEFERRED/blocked** → orientation omitted + annotated |

Confidence gate unchanged. Nothing is drawn from a `MEDIUM`/`review` string as geometry —
review-bucket items are label-only & flagged (same rule as DX `DistModel`/`DistOD`).

### 7.5 Phase split
- **5-pre (this) — DESIGN ONLY.** This §7: the table, convention extraction, new-primitive
  list, sourcing audit, split. No `src/`/test changes.
- **5a — table + composition + upstream sourcing (no new drawing geometry).**
  (1) `drawing_topology_rules.yaml` + a selector mapping `(category, header_type, special)`
  → feature spec; (2) refactor `build_dx_views` → `build_views(geom)` that branches on the
  table — **supply kind toggle** (`distributor` vs `plain_header`, both via existing
  primitives) is the only geometry change here; (3) UPSTREAM gated slots `slot.conn_angle`,
  `slot.vent_drain`, `slot.HGBP` (fail-closed); (4) sanitized fixtures per category
  (HGRH/CWC/HWC/HGBP — none exist today); (5) loader/gate/composition + mirror tests.
- **5b — per-category drawing + eyeball gate.** Implement the four new glyphs
  (`supply_header_port` manifold, `conn_angle_glyph`, `vent_port`/`drain_port`,
  `hgbp_bypass`) in layout + backend; render one EZC fixture per category; **human eyeball
  gate**; clean LH/RH mirror; **V1/V2/V3 DX unchanged**; retire static template dependency
  for covered categories.

**Acceptance (per §5):** one fixture per category (DX / HGRH / CWC / HWC + HGBP) renders the
correct feature set with no label collisions, every label leader-connected, clean LH/RH; the
static template path is retired for covered categories.

### 7.6 Constraints honored (Phase 5)
3-layer split kept; model in inches, datum/offset only; engine consumes gated slots only;
sourcing stays upstream; rules-as-data (YAML); one `mirror_view_x`; additive only (no schema
change that breaks the confidence gate); `export_allowed: False` + watermark preserved.

## Constraints honored

Three-layer split kept; model in inches, datum/offset only; engine consumes gated slots only;
connection-size sourcing stays upstream in the loader; EZ representation borrowed but **not**
`phase2a/renderer.py`'s x18/x16 scaling; front-view fields untouched; one `mirror_view_x`.
