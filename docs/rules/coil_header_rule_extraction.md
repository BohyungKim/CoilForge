# CoilForge — Coil Header Prepopulation Rule Extraction

**Sources of truth**
- `CHK` = Coil_Checklist_Template.xlsx (sheets: CWC, HWC, DX, HGRH, "Install | Drain Pan Width", Units). Evidence cited as `CHK <Sheet>!<Cell>` (formula in SUBMITTAL column C unless noted).
- `SOP` = 2024018 SOP – EZ Coil Selection, Rev I (Feb 10, 2026). Evidence cited as `SOP §<section>`. Sections: `§GEN` (Gathering Data & Cleaning Up Coil Selection), `§DX-TNVH` (Terra/Nova/Ventum H – DX), `§DX-VP` (Ventum+ – DX), `§HGRH-TNVH`, `§HGRH-VP`, `§CWC/HWC`.
- `SOP-OLE1..4` = the four identical embedded casing-depth tables (DX/HGRH): Rows 1–12 → CD = ROUNDUP(rows × 0.866 to nearest ⅛″) + 2″ (2.875 … 12.5).
- `SOP-OLE5` = embedded casing-depth table (CWC/HWC): Rows 1–12 → CD = ROUNDUP(rows × 1.299 to nearest ⅛″) + 2″ (3.375 … 17.625).

**Important discovery about the checklist:** the CHK SUBMITTAL column is formula-driven. It is itself a deterministic rule engine keyed on `C3` (product type), `C4` (unit size), `C5` (application), `C13/C14` (rows/feeds), `C15–C18` (conn size, qty conn/header), etc. This makes evidence extraction far stronger than expected — but it also exposes real conflicts with the SOP, listed below.

---

## 1. Executive Summary

**Verdict: header prepopulation is implementable, but NOT from the three requested inputs alone, and NOT uniformly across product types.**

**Feasible now (High confidence, both documents agree):**
- All per-coil-type constants: HF, RF, RB, suction HD, distributor I, distributor orientation, distributor extension, collared holes, stacking flanges, base NOTES strings.
- TF/BF for **Nova / Ventum H on DX & HGRH** (0.625″) and **Ventum+ on all coil types** (1″).
- SL values for Nova / Ventum H / Ventum+ (per coil type).
- CD lookup/formula structure (rows → CD), return stubout spacing formulas, multi-circuit CD equations — deterministic, but they require inputs beyond the three (rows, feeds/circuits, connection size).
- Unit-size enumeration and the Nova 1″-vs-2″ size classification (drives fit-margin selection).

**Not feasible / dangerous right now:**
- **Anything Terra.** This is the single largest finding. CHK models one product `TERRA`; the SOP (Rev I) distinguishes **Terra H, Terra H C, Terra V, and W-Ctrl vs D-Ctrl Terra**, with different values for I/O (2 vs 2.75 vs 3.25), SL (10 vs 12), distributor HD (0 vs 4.5), S-value conventions, and vent/drain options. CHK's Units sheet itself labels its Terra column "TERRA H C". The input `product_type` as defined is **insufficiently granular for Terra**.
- TF/BF for Terra (direct numeric conflict: SOP 0.625/0.625 vs CHK 1.625/0.375) and for Nova/Ventum H on CWC/HWC (SOP 1″ vs CHK 0.625″).
- Coating special-case note text (CHK predates SOP Rev H wording).
- ASC orientation for Hot Gas Bypass (SOP: "Left"; CHK: derived from handing LH→UP / RH→DOWN — different conventions).

**MVP scope (implement first):** the per-(coil_type × product_type) constant layer for **Nova, Ventum H, Ventum+ only**, plus unit-size validation/classification, plus deterministic formulas that surface as *suggestions with declared missing inputs*. Terra returns `review_required` wholesale until the variant question is resolved with Engineering.

---

## 2. Rule Extraction Table

Inputs referenced: `TC` = Type of Coil, `PT` = Product Type, `US` = Unit Size. `*` = applies to all values of that input. Field names follow CHK row labels (which match EZ Coil's Drawing tab).

### 2.1 Universal / per-coil-type constants

| Rule ID | Type of Coil | Product Type | Unit Size / Size Pattern | Required Header Information | Evidence Source | Confidence | Review Required | Notes |
|---|---|---|---|---|---|---|---|---|
| R-001 | * | * | * | collared_holes = TRUE (submittal) / FALSE (selection default) | SOP §GEN "Select Collared Holes"; CHK CWC!C18, HWC!C18, DX!C20, HGRH!C18 | High | No | Identical in both docs |
| R-002 | * | * | * | stacking_flanges = FALSE | SOP §GEN "Deselect Stacking Flanges and Lifting Lugs"; CHK all sheets (SELECTION=TRUE means EZ Coil default is on; SUBMITTAL=FALSE) | High | No | Lifting Lugs deselect is SOP-only (CHK has no row) → Medium sub-rule R-002b |
| R-003 | * | * | * | header_flange (HF) = 1.5 | SOP all sections "Leave Header Flange… default 1.5"; CHK *!HF `=1.5` | High | No | |
| R-004 | * | * | * | return_flange (RF) = 1.5 | Same as R-003 | High | No | |
| R-005 | DX, HGRH | * | * | return_bend (RB) = 1.5 (default; John 2026-06-25, was 1.75) | John 2026-06-25 (prior: SOP §DX-TNVH/§DX-VP/§HGRH-* ; CHK DX!C29, HGRH!C32) | High | No | 1.5 is now the direct-coil default across all product lines (drops OAL=FL+3+RB by 0.25); the old 1.75 with a "reduce to 1.5 if fit issue" escape hatch is superseded |
| R-006 | CWC, HWC | * | * | return_bend (RB) = 2.25 (min 1.875 if fit issue) | SOP §CWC/HWC; CHK CWC!C26, HWC!C30 | High | No | |
| R-007 | CWC, HWC | * | * | notes += "Vent & Drain installed <= 3\" from MPT connection. Only 1 Supply and 1 Return connection required. Do not bend connection to meet dimensional requirements." | SOP §GEN; CHK CWC!C20, HWC!C24 — strings match verbatim | High | No | |
| R-008 | DX, HGRH | * | * | notes += "Copper Straps Required." | SOP §GEN; CHK DX!C23, HGRH!C26 | High | No | |

### 2.2 Flanges (TF/BF) — the conflict zone

| Rule ID | Type of Coil | Product Type | Unit Size / Size Pattern | Required Header Information | Evidence Source | Confidence | Review Required | Notes |
|---|---|---|---|---|---|---|---|---|
| R-010 | DX, HGRH | NOVA, VENTUM H | * | TF = 0.625, BF = 0.625 | SOP §DX-TNVH "Nova, Ventum H: 0.625"; §HGRH-TNVH "0.625"; CHK DX!C27:C28, HGRH!C30:C31 | High | No | |
| R-011 | * (all 4) | VENTUM+ | * | TF = 1, BF = 1 | SOP §DX-VP, §HGRH-VP, §CWC/HWC "values to 1"; CHK *!TF/BF `IF(C3="VENTUM+",1,…)` | High | No | |
| R-012 / R-012v | DX, HGRH | TERRA | H C / V | TF = 1.625; BF = 0.5 (Terra H C, the default) or 0.375 (Terra V) | CHK `TERRA→TF=1.625`; John 2026-06-11 (checklist wins) then John 2026-06-25 (Terra H C BF 0.375→0.5; Terra V stays 0.375 via R-012v override) | High | Resolved | R-012 (terra_variant null) = Terra H C default 0.5; R-012v (terra_variant [TERRA_V]) overrides BF back to 0.375 (last-writer-wins by file order). |
| R-013 | CWC, HWC | NOVA, VENTUM H | * | TF/BF | SOP §CWC/HWC "Update TF and BF values to 1″" vs CHK `NOVA/VENTUM H→0.625` | **Conflict** | Yes | Direct numeric conflict between docs. **Do not prepopulate.** |
| R-014 / R-014v | CWC, HWC | TERRA | H C / V | TF = 1.625; BF = 0.5 (Terra H C) or 0.375 (Terra V) | CHK `TERRA→TF=1.625`; John 2026-06-25 (Terra H C BF 0.375→0.5; Terra V stays 0.375 via R-014v) | High | Resolved | Same pattern as R-012/R-012v for water coils |

### 2.3 Connection / stubout geometry

| Rule ID | Type of Coil | Product Type | Unit Size / Size Pattern | Required Header Information | Evidence Source | Confidence | Review Required | Notes |
|---|---|---|---|---|---|---|---|---|
| R-020 | DX | NOVA, VENTUM H, VENTUM+ | * | suction stubout I/O (O2/O4/O6/O8) = 2 | SOP §DX-TNVH & §DX-VP "Update all I/Os to 2″"; CHK DX!C30–C33 | High | No | Count of active O fields depends on qty_conn_per_header (missing input) |
| R-021 | DX | TERRA | * | suction stubout I/O | SOP "2″" (Terra V: 2.75) vs CHK `TERRA→3.25` | **Conflict** | Yes | 3.25 appears in SOP only in the Terra H C single-feed HGRH note → CHK "TERRA" likely means Terra H C. Variant granularity required. |
| R-022 | DX | * (non-Terra-V) | * | return stubout spacing: R1=D, R2=2D+1.5, R3=3D+3, R4=4D+4.5 (D = suction conn size) | SOP §DX-TNVH & §DX-VP; CHK DX!C34–C37 — formulas identical | High | No | Deterministic but needs suction_conn_size + qty_conn_per_header inputs |
| R-023 | DX | TERRA (V) | * | return spacing: Rn = (n−0.5)·D + 0.75(n−1)·… (SOP Terra V variant) | SOP §DX-TNVH SPECIAL CASE Terra V only; absent from CHK | Low | Yes | Single-source, requires Terra variant input |
| R-024 | DX | * | * | suction header HD (HD2/4/6/8) = 3.5 | SOP both DX sections; CHK DX!C38–C41 | High | No | |
| R-025 | DX | NOVA, VENTUM H | * | SL (suction, SL2/4/6/8) = 8 | SOP §DX-TNVH "8″ for Nova & Ventum H"; CHK DX!C42–C45 | High | No | |
| R-025b | DX | VENTUM H | H05, H10 | SL (suction, even SL2/4/6/8) = 17 (overrides R-025) | John 2026-06-26 | High | No | First rule to use `applies_to.size_pattern` (matching now active in `_applies`); even-slot clearance only |
| R-026 | DX | VENTUM+ | * | SL = 10 | SOP §DX-VP; CHK (`TERRA or VENTUM+ → 10`) | High | No | |
| R-027 | DX | TERRA | * | SL | SOP: 10 for **Terra H**, 12 for **Terra V**; CHK: `TERRA→10` | Medium | Yes | CHK matches Terra H only. Needs variant input. |
| R-028 | DX | NOVA, VENTUM H, TERRA | * | distributor I (I1/3/5/7) = 3 | SOP §DX-TNVH "Change all I values to 3″"; CHK DX!C50–C53 | High | No | |
| R-029 | DX | VENTUM+ | * | distributor I = 12 | SOP §DX-VP; CHK | High | No | |
| R-030 | DX | * | * | distributor HD (HD1/3/5/7) | SOP: 0″ for Nova/Ventum H/W-Ctrl Terra, 4.5″ for D-Ctrl Terra and Ventum+; CHK: `=4.5` unconditional | **Conflict** | Yes | CHK contradicts SOP for Nova/VH/W-Ctrl Terra. Also needs ctrl-type input for Terra. **Do not prepopulate.** |
| R-031 | DX | NOVA, TERRA, VENTUM H | * | dist_orientation = ConnectionDown ("DOWN") | SOP §DX-TNVH; CHK DX!C58 | High | No | |
| R-032 | DX | VENTUM+ | * | dist_orientation = ConnectionUp ("UP") | SOP §DX-VP; CHK DX!C58 | High | No | |
| R-033 | DX | * | * | dist_extension = 6 | SOP both DX sections; CHK DX!C59 `=6` | High | No | |
| R-034 | DX | * (non-Terra-V S-convention question) | * | distributor S values | SOP §DX-TNVH: "multiples of −3″" (Nova/VH/W-Ctrl Terra) vs CHK DX!C46–C49: even spacing `ROUND(k·CD/(C+1))` | **Conflict** | Yes | Two different placement conventions. CHK matches SOP's *D-Ctrl/Ventum+* "evenly space" guidance, not the −3″ rule. **Suggestion only.** |

### 2.4 HGRH-specific

| Rule ID | Type of Coil | Product Type | Unit Size / Size Pattern | Required Header Information | Evidence Source | Confidence | Review Required | Notes |
|---|---|---|---|---|---|---|---|---|
| R-040 | HGRH | * (non-Terra-V) | * | supply 1 I/O (I1) = 2 | SOP §HGRH-TNVH & §HGRH-VP; CHK HGRH!C33 `=2` | High | No | Terra V = 2.75 (SOP only → R-046) |
| R-041 | HGRH | NOVA, VENTUM H | * | return I/O (O*) = 2; round other supply I/Os up to integer | SOP §HGRH-TNVH; CHK HGRH!C37–C40 (`else 2`) | High | No | "Round up" needs default values from EZ Coil → suggestion-level |
| R-042 | HGRH | TERRA | * | return I/O | CHK `TERRA→3.25` vs SOP base text "2″" | **Conflict** | Yes | Same Terra-granularity issue (3.25 = Terra H C per SOP single-feed note) |
| R-043 | HGRH | * | * | HD (all) = 3.5 | SOP both HGRH sections; CHK HGRH!C50–C57 | High | No | |
| R-044 | HGRH | NOVA, VENTUM H | * | supply SL = 6, return SL = 8 | SOP §HGRH-TNVH; CHK HGRH!C59 return (8); supply SL1 CHK is computed `6 + D/2 − S1` | High (return) / Medium (supply) | Supply: Yes | CHK supply SL is geometric compensation for negative S; nominal 6 matches SOP. Suggest 6, flag formula. |
| R-044d | HGRH | VENTUM H | H05, H10 | return SL (even SL2/4/6/8) = 17 (overrides R-044b) | John 2026-06-26 | High | No | size_pattern-scoped; even-slot clearance only; supply SL1 unchanged (still geometric/Medium 6) |
| R-045 | HGRH | TERRA, VENTUM+ | * | return SL = 10 | SOP §HGRH-VP (10) + §HGRH-TNVH Terra-as-Terra-H; CHK `TERRA/VENTUM+→10` | High (VENTUM+) / Medium (TERRA) | Terra: Yes | Terra V = 12 per SOP only |
| R-046 | HGRH | TERRA (V) | * | I/O = 2.75, supply SL = 5, return SL = 12 | SOP §HGRH-TNVH Terra V special cases only | Low | Yes | Single-source (SOP Rev I), absent from CHK |
| R-047 | HGRH | * | * | supply conn_angle = LAS | SOP both HGRH sections "Change Conn Angle for all supply connections to LAS"; CHK single-feed note strings embed `SupConnAngle=LAS` | High | No | |
| R-048 | HGRH | * | * | S/R header positions: Return X = X·D + (X−1)·1.5; Supply = CD − [(Xmax+2)·D + (Xmax−1)·1.5] | SOP §HGRH-TNVH formulas; CHK HGRH!C42–C49 match (with Terra/Ventum+ branch differences) | Medium | Yes | CHK Terra/Ventum+ branches (`S=conn size`, `R=conn size`) differ from SOP general formula; Ventum+ SOP says "Change S/R values to match Conn Size" which matches CHK. Per-platform agreement is good but mixed → suggestion only |
| R-049 | HGRH | * | * | single_feed → header/stubout note string (per platform) | SOP §GEN SPECIAL CASE (4 platform variants incl. Terra H C, Terra V); CHK HGRH!C26 builds equivalent note for TERRA / NOVA·VH / VENTUM+ | Medium | Yes | Values consistent where comparable (e.g., Nova SL2=8, VP SL2=10, Terra O2=3.25 ↔ SOP Terra H C R1 I/O=3.25); CHK lacks Terra H vs H C vs V split |
| R-050 | HGRH | * | * | single_feed → Single Feed Ext. = 3 | SOP §HGRH-TNVH & §HGRH-VP SPECIAL CASE | Medium | Yes | SOP-only (CHK has no row) |
| R-051 | DX+HGRH pairing | * | * | HGRH FL & FH must match the paired DX coil | SOP §HGRH-TNVH/§HGRH-VP "Ensure FL & FH match DX Coil"; CHK HGRH rows DX FH / DX FL with equality warnings | High | No | Cross-coil validation rule, not a value rule; needs paired-coil inputs |

### 2.5 CWC / HWC-specific

| Rule ID | Type of Coil | Product Type | Unit Size / Size Pattern | Required Header Information | Evidence Source | Confidence | Review Required | Notes |
|---|---|---|---|---|---|---|---|---|
| R-060 | CWC, HWC | NOVA, VENTUM H, VENTUM+ | * | I/O = 2.3125 (multi-feed) | SOP §CWC/HWC "Update all I/Os to 2.3125″"; CHK `IF(TERRA,3.25,2.3125)` | High | No | Single feed → TBD (CHK) → R-064 |
| R-061 | CWC, HWC | TERRA | * | I/O | CHK `TERRA→3.25`; SOP base says 2.3125, Terra V special: supply 2.75 / return CH−2.75 | **Conflict** | Yes | Three different values across docs/variants. **Do not prepopulate.** |
| R-062 | CWC, HWC | * | * | HD = 4 (multi-feed); reduce if fit issue | SOP §CWC/HWC; CHK `IF(feeds=1,"N/A",4)` | High | No | Needs feeds input to decide N/A vs 4 |
| R-063 | CWC, HWC | NOVA, VENTUM H → 8; VENTUM+ → 10 | * | SL | SOP §CWC/HWC; CHK SL formula matches exactly for these platforms | High | No | TERRA→10 in CHK but SOP only specifies Terra V = 12 → Terra is Medium/review (R-065) |
| R-064 | CWC, HWC | NOVA/VENTUM H → 12; VENTUM+ → 14 | * | single_feed → SL override; I/O→"TBD"; HD→"N/A" | SOP §CWC/HWC SPECIAL CASE single feed (12/14); CHK SL `IF(C14=1,IF(VENTUM+,14,12),…)`, I/O TBD, HD N/A | High (SL) / Medium (TBD/N/A markers, CHK-only) | TBD/N/A: Yes | |
| R-065 | CWC, HWC | TERRA | * | SL | CHK `TERRA→10`; SOP silent for Terra H/H C, Terra V = 12 | Medium | Yes | |
| R-066 | CWC, HWC | * (non-Terra-V) | * | vent/drain: Supply 1 & Return 1 = "Connections" | SOP §CWC/HWC | Medium | Yes | SOP-only; CHK has no row |
| R-067 | CWC, HWC | TERRA (V) | * | vent/drain: Supply 1 & Return 1 = "HDR ENDS" | SOP §CWC/HWC SPECIAL CASE Terra V | Low | Yes | Single source, Rev I addition |
| R-068 | CWC, HWC | * | * | S/R = EZ Coil defaults (do not modify) | SOP §CWC/HWC "Leave all S/R as default values" | Medium | No | Prepopulation action = "no-op", safe |

### 2.6 Casing depth, casing dims, size classification

| Rule ID | Type of Coil | Product Type | Unit Size / Size Pattern | Required Header Information | Evidence Source | Confidence | Review Required | Notes |
|---|---|---|---|---|---|---|---|---|
| R-070 | DX, HGRH | * | * | CD base = ROUNDUP(rows × 0.866 to ⅛″) + 2 (rows 1–12 table) | SOP-OLE1..4; CHK DX!C24 / HGRH!C27 first MAX operand — formula reproduces table exactly | High | No | Needs `rows` input |
| R-071 | CWC, HWC | * | * | CD = ROUNDUP(rows × 1.299 to ⅛″) + 2 | SOP-OLE5; CHK CWC!C21 / HWC!C25 | High | No | Needs `rows` |
| R-072 | DX | * | * | CD multi-circuit: max(base, (C+1)·D + (C−1)·1.5) (DX-only) or C·(D+1.5)+(D−D_HGRH)/2 (w/ HGRH) | SOP §DX-TNVH & §DX-VP SPECIAL CASE equations; CHK DX!C24 MAX(...) — identical algebra | High | No | Needs circuits, suction conn size, with_hgrh, HGRH conn size |
| R-073 | HGRH | * | * | CD multi-header: SOP (C+1)·D+(C−1)·1.5; CHK adds branches VENTUM+→3·conn, TERRA→(H+2)·D+(H−1)·1.5+0.5 | SOP §HGRH-TNVH vs CHK HGRH!C27 | Medium | Yes | CHK branches are richer than SOP; no SOP backing for the Terra +0.5 / VP 3× variants |
| R-074 | * | NOVA(DECOUPLED), TERRA(INTEGRATED), VENTUM H(CPLD EXT / CPLD/DCPLD STD), VENTUM+(INTEGRATED), + 4 Nova HWC application variants | per Units sheet | casing_width / casing_height lookup by (PT, application, US) | CHK Units sheet + CASING WIDTH/HEIGHT XLOOKUP warning formulas (e.g., CWC!E7:E8, HWC!E7:E8) | Medium | Yes | Single source (CHK). SOP has no equivalent table. Deterministic and table-driven, but requires new `application` input. Units sheet labels the Terra column "TERRA H C". |
| R-075 | * | NOVA | A16, B20, C20, C24, C30 → "1-inch" class; A18, B22, C22, C26, C32, C40, C48, C58, C70 → "2-inch" class | size_class (drives fit margins) | SOP fit rules ("1″ Nova", "2″ Nova"); CHK WIDTH/HEIGHT FIT formulas enumerate the same size lists | High | No | The only place Unit Size deterministically changes header logic from the 3 core inputs |
| R-076 | * | * | per Units sheet | unit_size validation: NOVA {A16,A18,B20,B22,C20,C22,C24,C26,C30,C32,C40,C48,C58,C70}; TERRA H C {6,9,12,15,18,24,32,40,48}; VENTUM H {H05,H10,H15,H20,H25,H30}; VENTUM+ {V20,V25,V30,V40,V50,V60,V80,V100,V120,V150} | CHK Units sheet | High (as enumeration) | No | Terra V / Terra H sizes not enumerated anywhere → reject with review_required |
| R-077 | HWC, HGRH | * | per "Install \| Drain Pan Width" sheet | installed_on_drain_pan → drain-pan width / install width checks | CHK HWC rows 20–23 + INSTALL FIT; CHK Install sheet (Nova, Terra H C, Ventum H, Ventum+ tables; Terra V = "TBD"); SOP drain-pan special cases | Medium | Yes | Validation layer; needs installed_on_dp, CWC/DX CD inputs. Terra V explicitly TBD in CHK. |

### 2.7 Notes / special-case conflicts

| Rule ID | Type of Coil | Product Type | Unit Size / Size Pattern | Required Header Information | Evidence Source | Confidence | Review Required | Notes |
|---|---|---|---|---|---|---|---|---|
| R-080 | DX | * | * | coating ≠ NONE → notes += coating exclusion | SOP Rev H: "Do Not Coat Last 5-6 inches of Distributor Extensions"; CHK: "Do Not Coat Distributor Extensions." | **Conflict** | Yes | CHK predates SOP Rev H wording (Rev H authored by John Kim, Dec 2025). SOP wording should win, but flag for CHK update. |
| R-081 | HGRH | * | * | coating ≠ NONE → notes += coating exclusion | SOP Rev H: "…Last 5-6 inches **Supply Stubouts**"; CHK: "…Distributor Extensions." | **Conflict** | Yes | CHK uses DX wording for HGRH — wrong component named. SOP wins. |
| R-082 | DX | TERRA | * | notes += "Exclude mounting holes on the bottom flange only." (when with_hgrh per CHK condition) | CHK DX!C23 conditional; HGRH!C26 unconditional for TERRA | Low | Yes | CHK-only; no SOP backing; CHK conditions differ between DX (Terra AND w/HGRH) and HGRH (Terra) |
| R-083 | DX | * | * | hot_gas_bypass → ASC = selected | SOP §DX-TNVH SPECIAL CASE; CHK DX!C60 `=C7` | High | No | Needs hot_gas_bypass input |
| R-084 | DX | * | * | ASC orientation | SOP: "specify **Left** … same direction as return stubouts"; CHK: `LH→UP, RH→DOWN` from handing | **Conflict** | Yes | Different coordinate conventions; cannot reconcile from documents. Needs handing input either way. |
| R-085 | * | * | * | back-to-back coils → Mounting Holes, Bolts, 0.3125″, 12″ spacing | SOP §GEN SPECIAL CASE | Medium | Yes | SOP-only; needs back_to_back input |
| R-086 | DX, HGRH | * | * | coil_style from qty of valves: DX 1→Standard, 2→Interlaced 2 Circuits, 3→Interlaced 3, 4→Interlaced 4; HGRH 1→Standard, 2..4→Face Split N Circuits | SOP §GEN | Medium | Yes | SOP-only; needs qty_valves input; arguably selection-tab not header, include behind flag |

---

## 3. Header Field Definition

Proposed `header_prepopulate` output schema fields (grouped; names snake_case for Pydantic):

**Identity / context**
- `coil_type_label` — DX | HGRH | CWC | HWC
- `product_family` — NOVA | TERRA | VENTUM_H | VENTUM_PLUS (+ `terra_variant`: TERRA_H | TERRA_H_C | TERRA_V | UNKNOWN, and `terra_ctrl_type`: W_CTRL | D_CTRL | UNKNOWN — see §4)
- `unit_size_label` — validated against R-076 enumerations
- `size_class` — NOVA_1IN | NOVA_2IN | N/A (R-075)

**Flange / casing block**
- `casing_depth` (computed; requires rows [+circuits/conn for DX, headers/conn for HGRH])
- `header_flange`, `return_flange`, `top_flange`, `bottom_flange`, `return_bend`
- `casing_width`, `casing_height` (lookup; requires application)

**Connection arrangement**
- `connection_arrangement` — structured: per-header `io`, `hd`, `sl`, `s_position`, `r_position`, `conn_angle`, `qty_conn_per_header`
- `dist_orientation`, `dist_extension`, `dist_i_value`, `dist_hd_value`
- `handedness` — LH | RH (input passthrough; never inferred)
- `single_feed_ext`
- `vent_drain_option` — CONNECTIONS | HDR_ENDS

**Options / notes**
- `collared_holes`, `stacking_flanges`, `lifting_lugs`, `asc`, `asc_orientation`, `mounting_holes_spec`
- `special_notes` — ordered list of note strings (base + conditional appends)
- `coil_style` (behind feature flag, R-086)

**Engine metadata (per field, not global)**
- `confidence` — HIGH | MEDIUM | LOW | CONFLICT
- `evidence_refs` — list of rule IDs → source citations
- `review_required` + `review_required_reason`
- `missing_inputs` — inputs that would unlock the field
- `blocked_reason` — populated for CONFLICT/LOW

---

## 4. Missing Input Analysis

The three core inputs determine only the constant layer (§2.1–2.3 High rules). Everything else needs at least one of:

| Missing input | Unlocks | Evidence it's required |
|---|---|---|
| `terra_variant` (Terra H / Terra H C / Terra V) **+ `terra_ctrl_type` (W-Ctrl / D-Ctrl)** | All Terra rules: I/O, SL, dist HD, S-convention, vent/drain, Terra V formulas | SOP Rev I Terra V sections; SOP W-Ctrl/D-Ctrl branches; CHK Units "TERRA H C" label |
| `application` (DECOUPLED, INTEGRATED, CPLD EXT, CPLD/DCPLD HORZ/VERT/STD, STANDALONE, CPLD W/ COOLING) | casing_width/height lookup (R-074); HWC has 4 Nova variants | CHK CASING WIDTH/HEIGHT XLOOKUP formulas |
| `rows` | CD (R-070/071) | CHK CD formulas; SOP-OLE tables |
| `feeds` (total feeds; detects single-feed) | CWC/HWC HD vs N/A, SL override, I/O TBD, HGRH single-feed notes, Single Feed Ext. | CHK `C14` branches; SOP single-feed special cases |
| `qty_conn_per_header` / `circuits` | DX/HGRH active header count (O4/O6/O8…), multi-circuit CD, R/S positions | CHK `C18` (DX), `C16` (HGRH) branches; SOP circuit equations |
| `suction_conn_size` (DX) / `conn_size` (HGRH) / in-out conn sizes (CWC/HWC) | R positions, multi-circuit CD, S/R values | CHK `C17`/`C15`; SOP formulas use D |
| `handing` (LH/RH) | handedness passthrough; ASC orientation (conflicted anyway) | SOP "Refer to the sales drawing to confirm the handing"; CHK validation list LH,RH |
| `coating` (enum, 14 values) | coating note appends (R-080/081) | CHK dropdown; SOP Rev B/H special cases |
| `with_hgrh` (DX) | CD equation choice; HGRH conn size requirement | CHK DX!C6; SOP DX w/ HGRH equation |
| `hot_gas_bypass` (DX) | ASC selection (R-083/084) | CHK DX!C7; SOP Rev E special case |
| `installed_on_drain_pan` (HWC/HGRH) | install/drain-pan width checks (R-077) | CHK rows + INSTALL FIT |
| `fh`, `fl` | OAL/CH computation and fit checks; HGRH must match paired DX | CHK OAL/CH formulas; SOP "Ensure FL & FH match DX Coil" |
| `back_to_back`, `qty_valves` | R-085, R-086 | SOP-only special cases |

**Design consequence:** the engine contract must return `missing_inputs` per field, not refuse globally — the constant layer is still fully servable from the 3 core inputs.

---

## 5. Codex Implementation Handoff

**Recommended files**
- `docs/rules/coil_header_rule_extraction.md` — this document (source-of-truth citation map)
- `src/coilforge/rules/coil_header_rules.yaml` — rule table serialized: one entry per Rule ID with `applies_to {coil_type, product_family, terra_variant?, size_pattern?}`, `field`, `value | formula`, `confidence`, `evidence_refs`, `requires_inputs`, `review_required`, `blocked_reason?`
- `src/coilforge/schemas/header_prepopulate.py` — Pydantic models: `HeaderPrepopulateRequest`, `FieldResult` (value, confidence, evidence_refs, review_required, reason), `HeaderPrepopulateResponse` (fields, missing_inputs, blocked, blocked_reason)
- `src/coilforge/services/header_prepopulate_engine.py` — pure-function rule evaluation; no I/O, no Epicor/export calls
- `tests/test_header_prepopulate_engine.py` — golden cases from §6, written **before** the engine

**Required engine behavior**
- Input: `type_of_coil`, `product_type`, `unit_size` (+ optional extended inputs from §4)
- Output: prepopulated header fields, per-field confidence, evidence_refs, missing_inputs, review_required, blocked_reason
- **High confidence → auto-prepopulate.**
- **Medium → returned under `suggestions`, never `values`, with `review_required=true`.**
- **Low / Conflict → never populated; return `blocked` with `blocked_reason` quoting both evidence refs.**
- `product_type=TERRA` without `terra_variant` → all Terra-dependent fields return `review_required=true`, `blocked_reason="terra_variant_unresolved"`. Constants that are genuinely Terra-invariant per both docs (HF, RF, RB, suction HD, dist I=3, orientation DOWN, dist ext 6, collared holes, stacking flanges, copper-straps note) may still populate High.
- `unit_size` not in the R-076 enumeration for the product → `blocked_reason="unknown_unit_size"`.
- Formula rules (CD, R-positions) evaluate only when all `requires_inputs` are present; otherwise the field reports its `missing_inputs` and stays empty.
- **No modification of existing CoilForge export logic. Header prepopulation only.**

---

## 6. Golden Test Cases

All expected values trace to Rule IDs above. Confidence shown is the dominant per-field gate.

**T01 — DX / NOVA / B20 (happy path, 1″ class)**
Given: DX, NOVA, B20
Expected: rb=1.5 (R-005), tf=0.625, bf=0.625 (R-010), suction hd=3.5 (R-024), sl=8 (R-025), dist i=3 (R-028), dist_orientation=DOWN (R-031), dist_extension=6 (R-033), io_suction=2 (R-020), collared_holes=TRUE (R-001), stacking_flanges=FALSE (R-002), notes=["Copper Straps Required."] (R-008), size_class=NOVA_1IN (R-075); dist_hd → blocked CONFLICT (R-030); Confidence=High on listed fields; Review Required=false except dist_hd; Evidence: SOP §DX-TNVH + CHK DX sheet.

**T02 — DX / NOVA / A18 (2″ class)**
Same as T01 except size_class=NOVA_2IN (R-075). Evidence: CHK fit formulas + SOP "2″ Nova" rules.

**T03 — DX / VENTUM+ / V40**
Expected: tf=1, bf=1 (R-011), sl=10 (R-026), dist i=12 (R-029), dist_orientation=UP (R-032), rb=1.5, hd_suction=3.5, dist_extension=6, io=2 (R-020); dist_hd: SOP §DX-VP says 4.5 and CHK says 4.5 → for VENTUM+ specifically both agree → value 4.5, Confidence=High (R-030 conflict applies only to Nova/VH/W-Ctrl Terra); Review=false. Evidence: SOP §DX-VP + CHK.

**T04 — DX / VENTUM H / H15**
Expected: tf/bf=0.625, sl=8, dist i=3, orientation=DOWN, io=2; dist_hd blocked (CONFLICT R-030: SOP=0 vs CHK=4.5). Review on dist_hd=true. Evidence: SOP §DX-TNVH vs CHK DX!C54.

**T05 — DX / TERRA / 24 (Terra gate)**
Expected: hf/rf=1.5, rb=1.5, hd_suction=3.5, dist i=3, orientation=DOWN, dist_ext=6, notes copper straps → High (Terra-invariant). io_suction → blocked CONFLICT (R-021: SOP 2 vs CHK 3.25). sl → suggestion 10, review_required=true (R-027). tf/bf → blocked CONFLICT (R-012). Global: review_required=true, blocked_reason includes "terra_variant_unresolved". Evidence: SOP §DX-TNVH vs CHK DX.

**T06 — DX / NOVA / B20 with rows=4, circuits=1, suction_conn=0.875**
Expected: cd = max(5.5, 2×0.875) = 5.5 (R-070 table row 4 + R-072), Confidence=High, Evidence=SOP-OLE1 + CHK DX!C24.

**T07 — DX / NOVA / B20 with rows=4, circuits=3, suction_conn=1.625**
Expected: cd = max(5.5, (3+1)×1.625 + 2×1.5) = max(5.5, 9.5) = 9.5 (R-072 DX-only equation). r1=1.625, r2=4.75, r3=7.875 (R-022). Confidence=High.

**T08 — HGRH / NOVA / C20**
Expected: i1=2 (R-040), o=2 (R-041), hd=3.5 (R-043), supply_sl=6 (suggestion, Medium R-044), return_sl=8 (High R-044), conn_angle=LAS (R-047), tf/bf=0.625 (R-010), rb=1.5, notes copper straps. Evidence: SOP §HGRH-TNVH + CHK HGRH.

**T09 — HGRH / VENTUM+ / V20**
Expected: tf/bf=1 (R-011), return_sl=10 (R-045 High), supply_sl=6 (Medium suggestion), hd=3.5, i1=2. Evidence: SOP §HGRH-VP + CHK.

**T10 — HGRH / TERRA / 12**
Expected: hd=3.5, conn_angle=LAS, rb=1.5 High; o → blocked CONFLICT (R-042); return_sl → suggestion 10 review=true (R-045); tf/bf blocked (R-012); terra_variant_unresolved. Evidence: SOP vs CHK HGRH.

**T11 — HGRH / NOVA / C20 with feeds=1**
Expected: single-feed note suggestion containing "Add Headers & Stubouts… O2=2… SL2=8" pattern, review_required=true (R-049 Medium); single_feed_ext=3 suggestion (R-050 Medium). Evidence: SOP §GEN single-feed note (Nova variant) + CHK HGRH!C26.

**T12 — CWC / NOVA / A16**
Expected: rb=2.25 (R-006), hf/rf=1.5, io=2.3125 (R-060, requires feeds>1 → if feeds absent: suggestion with missing_inputs=[feeds]), sl=8 (R-063), hd=4 (R-062, same feeds caveat), notes vent&drain (R-007), size_class=NOVA_1IN; tf/bf → blocked CONFLICT (R-013: SOP 1 vs CHK 0.625). Evidence: SOP §CWC/HWC vs CHK CWC.

**T13 — CWC / VENTUM+ / V30**
Expected: tf/bf=1 (R-011 — both docs agree for VENTUM+), rb=2.25, sl=10 (R-063), io=2.3125, hd=4. Confidence=High. Evidence: SOP §CWC/HWC + CHK.

**T14 — HWC / VENTUM+ / V60 with feeds=1**
Expected: sl=14 (R-064 High), io="TBD" suggestion review=true, hd="N/A" suggestion review=true. Evidence: SOP single-feed (14″ Ventum+) + CHK SL/IO/HD formulas.

**T15 — HWC / NOVA / C30 with feeds=2, rows=2**
Expected: sl=8, io=2.3125, hd=4, cd=4.625 (R-071: ROUNDUP(2×1.299×8)/8+2 = 2.625+2). Confidence=High. Evidence: SOP-OLE5 + CHK HWC!C25.

**T16 — CWC / TERRA / 18**
Expected: rb=2.25, hf/rf=1.5, notes vent&drain High; io blocked CONFLICT (R-061); sl suggestion 10 review=true (R-065); tf/bf blocked (R-014); terra_variant_unresolved. Evidence: SOP vs CHK CWC.

**T17 — DX / NOVA / B20 with coating=HERESITE**
Expected: notes = ["Copper Straps Required.", coating note] but coating note → blocked CONFLICT (R-080: SOP Rev H wording vs CHK wording); engine must not silently pick either. Review=true. Evidence: SOP Rev H entry vs CHK DX!C23.

**T18 — DX / NOVA / B20 with hot_gas_bypass=true, handing=LH**
Expected: asc=selected (R-083 High); asc_orientation → blocked CONFLICT (R-084: SOP "Left" vs CHK LH→UP). Evidence: SOP Rev E special case vs CHK DX!C61.

**T19 — DX / VENTUM H / H99 (invalid size)**
Expected: blocked, blocked_reason="unknown_unit_size" (R-076). No fields populated. Evidence: CHK Units sheet enumeration.

**T20 — CWC / NOVA / A16 with application=DECOUPLED**
Expected: casing_width=34, casing_height=20 as Medium suggestion review=true (R-074, single-source CHK Units!B4:C4). Evidence: CHK CWC!E7:E8 XLOOKUP + Units sheet.

---

## 7. Final Recommendation

**MVP — implement now (Phase 1):**
1. Input validation layer: coil-type enum, product enum, unit-size enumeration per product (R-076), Nova size classification (R-075).
2. High-confidence constant layer for **NOVA, VENTUM H, VENTUM+**: R-001…R-008, R-010, R-011, R-020, R-024…R-029, R-031…R-033, R-040, R-041, R-043…R-045(VP), R-047, R-060, R-062, R-063, R-064(SL), R-083, plus VENTUM+ dist_hd=4.5 (per-platform agreement).
3. Terra-invariant constants for TERRA (HF/RF/RB/suction HD/dist I/orientation/dist ext/notes-base/collared/stacking), everything else Terra → `review_required`.
4. Formula rules behind `missing_inputs` reporting: R-070/071/072 (CD), R-022 (R-positions).
5. Medium rules exposed only as `suggestions`: R-044(supply SL), R-049/050, R-065/066, R-068, R-073, R-074, R-077, R-085, R-086.

**Do NOT implement yet (dangerous):**
- Any Terra value rule keyed only on `product_type=TERRA` (R-012, R-021, R-027 auto, R-042, R-061, R-065 auto, R-046, R-067, R-023). Resolve `terra_variant` + W-Ctrl/D-Ctrl with Engineering first — CHK and SOP demonstrably encode *different Terra products*.
- TF/BF for Nova/Ventum H on CWC/HWC (R-013) and Terra everywhere (R-012/R-014) until the SOP-vs-checklist numbers are reconciled.
- DX distributor HD (R-030) and distributor S convention (R-034).
- Coating note text (R-080/081) — recommend updating the checklist to SOP Rev H wording first, then promote to High.
- ASC orientation (R-084) until the Left-vs-UP/DOWN convention is unified.

**Process recommendation:** the five conflict clusters (Terra granularity, TF/BF, dist HD/S, coating wording, ASC) are exactly the items to take to the SOP owner (Jake Kalina / David Newton) before any auto-prepopulation touches them. Each is a 1-line confirmation that converts a Conflict rule to High.
