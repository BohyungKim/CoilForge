# CCSI Direct Coil — DX form structure (Phase 0 capture)

Captured live 2026-09-25 from `coil.ccsi.ie/Coils/Edit/{coilId}` (project 2803, CDXC-1),
read-only DOM dump via Claude-in-Chrome. No value changed, Calculate not clicked.
Form version: `Version:1.0.1 (web version)`.

Status of every mapping below: **captured** (inferred from label + ledger key names;
review-required until validated against past projects and confirmed by John).
`RO` = `readOnly` in the live DOM at capture time. No field on this form has an
`<id>_isActive` toggle (unlike the drawing-dimension grid).

## Access boundary (Confirmed)

A coil can be opened only inside a project the logged-in user owns. For another user's
project (2667, created by `melody@oxygen8.ca`) the product rows carry no `editProduct`
link and `/Coils/Edit/{id}` returns *Access Denied*. John's account lists 3 projects.

## DX COIL DATA

| CCSI id | Label | Kind | Candidate canonical path |
|---|---|---|---|
| `Tag` | Tag | text | `tag` |
| `CoilQuantity` | Coil Quantity | number | `quantity` |
| `TubeDiameter` | Tube Diameter | select (7) | `geometry.tube_diameter_od` + `tube_geometry` (composite) |
| `TubesHigh` | Tubes High | number **RO** | computed from FH |
| `FinnedHeight` | Finned Height (in) | number | `geometry.finned_height` |
| `FinnedLength` | Finned Length (in) | number | `geometry.finned_length` |
| `RowsDeep` | Rows Deep | select, has **Optimise** | `geometry.rows_deep` |
| `FinsPerInch` | Fins Per Inch | select, has **Optimise** | `geometry.fins_per_inch` |
| `NumberOfFeeds` | Number Of Feeds (Total) | number | `geometry.number_of_feeds` |

## OPTIONS

| CCSI id | Label | Vocabulary (option text) | Candidate canonical path |
|---|---|---|---|
| `TubeMaterial` | Tube Material | Copper {0.012,0.014,0.016,0.020,0.025} {Plain,Rifled} | `tube_material` value (wall) + unit (material) + canonical `tube_surface` — `option_material_gauge` (D1) |
| `FinMaterial` | Fin Material | Aluminum {0.005..0.010}, Coated aluminum 0.006, Copper {0.005..0.010} | `fin_material` value (gauge) + unit (material) — `option_material_gauge` (D1) |
| `FinSurface` | Fin Surface | Corrugated ; Lanced ; Flat | `materials_construction.fin_surface` |
| `HeaderMaterial` | Header Material | Copper | `materials_construction.header_material` |
| `HeaderWallSchedule` | Header Wall Schedule | (K) ; (L) | `materials_construction.header_wall_schedule` |
| `ConnectionMaterial` | Connection Material | Copper | `connections.connection_material` |
| `RefrigerantConnectionType` | Connection Type | Sweat | `connections.connection_type` |
| `DXReturnConnectionSize` | Return Connection Size | Calculate ; 1/2" … 3 1/8" | `connections.return_connection_size` (decimal → fraction) |
| `CasingStyle` | Casing Style | Stacking ; Standard ; Inverted ; Shipping Covers | `materials_construction.casing_style` |
| `CasingMaterial` | Casing Material | Galvanized Steel {14,16,18} gauge, Stainless {16,18}, Aluminum {0.051,0.063,0.080}, Copper | `materials_construction.casing_material` |
| `ConnectionEnds` | Connection Ends | Same End Only ; Any ; Opposite End Only | `connections.connection_ends` |
| `CoilCoating` | Coil Coating | Plain ; AA Coating | `manufacturing_options.coil_coating` |
| `CoilHand` | Coil Hand | Right ; Left | `connections.coil_hand` |
| `RefrigerationSystemType` | System Type | Single-Circuit ; Dual-Circuit Intertwined[(uneven)] ; Dual-Circuit Face-Split[(uneven)] ; 3-Circuit Intertwined[(uneven)] ; 3-Circuit Face-Split[(uneven)] ; 4-Circuit Face-Split ; 2 Circ Int + 2 Circ Int | `manufacturing_options.system_type` |
| `DraintrayTypeAlt` | Drain Pan Type | None ; Intermediate | `manufacturing_options.drain_pan_type` |
| `DraintrayMaterialAlt` | Drain Pan Material | SST ; GALV | — (no canonical field) |
| `DrawingNotes` | Drawing Notes | free text | existing top-level `drawing_notes` payload key |

## AIR DATA

| CCSI id | Label | Kind | Candidate canonical path |
|---|---|---|---|
| `TotalAirFlow` | Total Air Flow (CFM) | number | `airside_conditions.total_air_flow_cfm` |
| `ACFM` | (unit basis) | select: Standard ; Actual | — |
| `AirFlowPerCoil` | Air Flow Per Coil (CFM) | number | — |
| `FaceVelocity` | Face Velocity (FPM) | number | `airside_conditions.face_velocity_fpm` |
| `Altitude` | Altitude (FT) | number **RO** | `airside_conditions.altitude_ft` |
| `EnteringDryBulb` | Entering Dry Bulb (°F) | number | `airside_conditions.entering_dry_bulb_f` |
| `EnteringWetBulb` | Entering Wet Bulb (°F) | number | `airside_conditions.entering_wet_bulb_f` |
| `EnteringRelativeHumidity` | Entering RH (%) | number | `airside_conditions.relative_humidity_pct` |
| `LeavingDryBulb` | Leaving Dry Bulb (°F) | number **RO** | `airside_conditions.leaving_dry_bulb_f` |
| `Capacity` | Total Capacity (MBH) (Per Coil) | number **RO** | `performance.total_capacity_mbh` |

## REFRIGERANT DATA / FOULING

| CCSI id | Label | Vocabulary / kind | Candidate canonical path |
|---|---|---|---|
| `Refrigerant` | Refrigerant | R134a ; R22 ; R290 ; R32 ; R404A ; R407A/C/F ; R410a ; R448A ; R449A ; R454A/B/C ; R502 ; R507A ; R508B ; R513A ; R600A ; R744 ; R452B ; R1234yf ; R515B | `refrigerant_conditions.refrigerant` |
| `EvaporatingTemperature` | Evaporating Temp (°F) | number | `refrigerant_conditions.evaporating_temp_f` |
| `LiquidTemperature` | Liquid Temp (°F) | number | `refrigerant_conditions.liquid_temp_f` |
| `Superheat` | Superheat (°F) | number | `refrigerant_conditions.superheat_f` |
| `DXDistCapillarySize` | Capillary Diameter | 3/16 ; 1/4 ; 5/16 x 0.025 | `refrigerant_conditions.dx_dist_capillary_size` |
| `AirSideFoulingFactor` | Air Side Fouling Factor | number | — |

Action: `calcBtn` (Calculate). Distributor hidden fields exist (`DXDist{1..4}{Feeds,Model,Nozzle,ASC}`, `DXDistCycleValve`, `DXDistCircuitDraining`) — filled by CCSI after Calculate.

## Open (needs John)

1. **Computed outputs not yet captured** — the results shown after Calculate (capacity, LAT, air/refrigerant PD, distributor) need one Calculate click by John on an owned coil.
2. The three RO air fields (`Altitude`, `LeavingDryBulb`, `Capacity`) — unknown whether a mode switch makes one of them an input.
3. `Optimise` on Rows/FPI = CCSI can do true selection; out of scope for Rating mode.

## First vocabulary gaps seen against the ledger (3025 CDXC-1 draft stage)

| Field | Ledger value | CCSI expects |
|---|---|---|
| `refrigerant` | `R-32` | `R32` |
| `system_type` | `Heat Recovery System` | no such option (circuit arrangement vocabulary) |
| `fin_material` | `0.008`, unit `Aluminum` (material rides in the unit — D1) | `Aluminum 0.008` |
| `tube_material` | `0.016`, unit `Copper` + tube surface `Smooth` (D1) | `Copper 0.016 Plain` |
| `return_connection_size` | `1.125` | `1 1/8"` |
| `tube_diameter_od`, `tubes_high`, `header_material`, `casing_*` | unmapped | — |
