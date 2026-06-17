# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What CoilForge is

An internal coil-engineering tool that turns captured coil inputs (a "Direct Coil"
form, a submittal document, or a scanned EZ Coil / CoilMaster PDF) into a populated
**review-aid** drawing, a paste-ready field set, and a validation/compatibility report.
It is not selection software and not a manufacturing-drawing release system.

Read `AGENTS.md` before changing anything — it defines the project's hard boundaries
and the required report-back format. The most load-bearing rules:

- Never modify raw JSON or raw PDF files; never invent engineering values.
- Inferred mappings are **review-required** until John (the engineer/owner) or
  engineering confirms them — never treat them as confirmed.
- Generated drawings are review aids until formally approved; do not claim approval
  or enable production export.
- Do not build the full selection-calculation engine unless explicitly approved.

## Commands

Tests run from the repo root; each test file inserts `src/` onto `sys.path`, so there
is no install step or `pyproject.toml`.

- Full suite: `python -m pytest -q`
- Single file: `python -m pytest tests/test_header_prepopulate_engine.py -q`
- Single test: `python -m pytest tests/test_header_prepopulate_engine.py::test_name -x`
- Run the local web app (Windows, port 8011): double-click / run `run_server.bat`
- Run the web app manually: `python -m uvicorn coilforge.web_app:app --app-dir src --reload`
  (the README's `coilforge.phase2a.app:app` entrypoint also works; `web_app` extends it)

Runtime deps that may need installing: `python -m pip install fastapi uvicorn pyyaml pydantic`.
PDF intake uses PyPDF2. Tests `pytest.importorskip("fastapi")` so they degrade gracefully.

## Trigger keywords

**`shipit`** — "tests-green, then commit + push, in one go." When John types `shipit`
(alone or in a message), do exactly this, in order, and stop at the first failure:

1. Run the full suite: `python -m pytest -q`.
2. **Gate:** proceed only if the run is green. The tree currently has 4 known
   pre-existing `phase2c` PO-logic reds — `shipit` treats the run as passing only when
   the *only* failures are those 4 documented reds and nothing in the files you changed
   regressed; any new/other failure → **STOP, report it, commit nothing.** (To require a
   fully-green run instead, say `shipit strict`. To scope to the drawing work, say
   `shipit drawing` → run only `tests/test_schematic_renderer.py`.)
3. Stage **only the files for the current work** — review `git status` first and `git add`
   those paths explicitly. **Never `git add -A`**: this worktree carries unrelated edits
   from a concurrent session that must not be swept into the commit.
4. Commit with a Conventional Commit subject (`feat:`/`fix:`/`refactor:`/`docs:`…) and the
   `Co-Authored-By: Claude …` trailer.
5. Push: first push on this branch needs `git push -u origin <current-branch>`; later
   pushes are plain `git push`.

**Hard guards (never bypass, even with `shipit`):** never push to `main`; never
`--force`/`--force-with-lease`; never `--no-verify`; never amend an already-pushed commit.
For drawing-engine changes the Phase-Gate eyeball approval still applies — John typing
`shipit` *is* that approval for the change in hand; it does not pre-approve future work.

## Architecture — the big picture

Two input tracks converge on a shared canonical model, then fan out to drawings.

**Track A — Direct Coil form → drawing** (`services/direct_coil_drawing_pipeline.py`):
1. `build_header_request(...)` — coil inputs → `HeaderPrepopulateRequest`.
2. `prepopulate(request)` — the YAML rule engine (see below).
3. `build_drawing_slots(...)` — resolve **every** dimension slot from a mechanical
   value (engine HIGH value, recovered formula, coil input, or exact EZ JSON override).
4. `select_drawing_template` + `populate_template_slots` → SVG.

**Track B — submittal/PDF → drawing** (`workflows/submittal_to_drawing.py`):
submittal text or PDF bytes → `SubmittalCoilCandidate` → `CanonicalCoilRecord`
→ `DirectCoilInputDraft` → resolved drawing parameters → SVG preview. The PDF path
additionally calls `submittal/pdf_to_template_drawing.py` to read as-built values
straight off the scanned drawing into a template-first drawing.

**The header rule engine** (`services/header_prepopulate_engine.py` +
`rules/coil_header_rules.yaml`) is the heart of the system. It is a pure, deterministic
function with one I/O (loading the cached YAML rule table). Rules are identified by IDs
(`R-070`, etc.); most go through a generic constant/conflict emitter, but a set of
`_SPECIAL_IDS` (casing depth, return spacing, CWC/HWC io/hd/sl, notes assembly, etc.)
are handled by dedicated phase helpers. Formulas use explicit safe helpers — **never
`eval`**. When changing engineering behavior, edit the YAML rule and/or its helper, not
ad-hoc code elsewhere.

**The confidence gate is the central invariant.** Every rule carries a confidence that
routes its output (`bucket_for_confidence`):
- `HIGH` → `values` — auto-prepopulated / drawn.
- `MEDIUM` → `suggestions` — always `review_required`, surfaced but never silently drawn.
- `LOW` / `CONFLICT` → `blocked` — `value=None` with a `blocked_reason`.
This gate is enforced again at the data-contract layer and must be preserved end to end.

**Data contracts** (`contracts/`) — every imported/prepopulated value is wrapped:
- `FieldValue` — traceable value with `source_evidence`, `confidence`, `status`,
  `review_required`. Its validator **requires `source_evidence` for any non-null,
  non-override value** — you cannot smuggle in a bare value. Keep raw source evidence
  separate from normalized interpretation.
- `CanonicalCoilRecord` — the internal source of truth; auto-collects
  `review_required_fields` / `blocked_fields` from its `FieldValue` members.
- `SubmittalCoilCandidate` (`submittal/candidate.py`) — the pre-canonical extract.

**Templates** (`templates/drawing/coilmaster/<category>/<id>/template.svg`) are real
CoilMaster-format SVGs with engineering values redacted to named slots (`slot.CD`,
`slot.HD2`, `slot.I1`, …). `template_population/` selects a template
(`catalog.ACTIVE_TEMPLATES`, keyed by supplier/category/hand/header type), populates
slots (`slot_population.py`), and mirrors LH↔RH (`mirror.py`). Each template is either
seeded from a provided PDF or mirrored from a seeded pair — both are review-aid only.
Schemas for the catalog / slot map live in `schemas/*.schema.json`.

**Web app** — `coilforge/web_app.py` imports the Phase 2A FastAPI `app` and registers
the `/api/*` routes (workflows, compatibility review, decision capture, review packets).
The browser UI is vanilla JS in `web/` (`index.html` / `app.js` / `style.css`). API
responses deliberately assert safety flags (`raw_private_data_returned: False`,
`export_allowed: False`, `production_drawing_approval_claimed: False`).

## Conventions

- Python 3.11+, `from __future__ import annotations`, full type hints, Pydantic v2
  with `ConfigDict(extra="forbid")` on data models.
- Engineering logic is rule/data-driven and must stay explainable: prefer adding a YAML
  rule with `evidence_refs` over hardcoding a value in Python.
- Tests are organized by phase (`test_phase2a_*` … `test_phase2e_*`) plus feature-named
  files. There are 400+ tests; run the full suite before claiming a task is done.
- `.gitignore` blocks raw customer data by pattern (`*.pdf`, `*.xlsx`, `Case/`,
  `*_raw.json`, rendered PNG/JPG). Only sanitized fixtures under `examples/sanitized/`
  belong in the repo.

## Drawing engine (parametric — in progress)

The current submittal path fills a fixed SVG template via text substitution (static
geometry — a coil with FL=120" draws the identical box as FL=20"). We are building a
**parametric drawing engine** that redraws the coil to scale from resolved dimensions,
targeting three first-class outputs: **SVG** (web review aid), **DXF** (shop / CAD
handoff), and **PDF** (customer submittal).

### Architecture — non-negotiable

1. **Three layers, never collapsed.** geometry model -> layout/datum engine ->
   renderer backend. Rendering code must not compute geometry; layout code must
   not emit SVG/DXF/PDF.
2. **Model is in real-world units (inches).** The geometry model and datum engine
   carry true dimensions only — never pixels. Presentation scale lives in the
   backend (see Output backends). One model, three backends.
3. **Backend-swappable renderer.** SVG, DXF, and PDF backends all consume the same
   geometry model. Adding or changing a backend must not touch the model or
   layout layers. The model emits no renderer-specific types.
4. **Input contract = gated `slot_values` only.** The engine consumes dimensions
   already resolved and confidence-gated upstream (`slot.FH`, `slot.FL`,
   `slot.CH`, `slot.CL`, `slot.CD`, `slot.HF`, header offsets...). Validation
   stays upstream. The engine never invents a value: `None` / "REVIEW REQUIRED"
   -> feature omitted and annotated, never guessed.
5. **Datum/offset only — no absolute coordinates.** Every feature is placed
   relative to computed datums (the "grid"). Doubling any dimension must move all
   dependent features coherently. Hardcoded path coordinates are a defect.
6. **No constraint solver / CAD kernel.** Deterministic recompute only. Do not
   add an iterative or symbolic solver unless explicitly requested.
7. **Aspect ratio preserved.** Scaling is uniform — never scale x and y
   independently. That is the bug in `phase2a/renderer.py` (x18 / x16) we are not
   repeating.

### Output backends

The model holds inches; each backend decides how to present them:

- **SVG (review aid):** uniform `px_per_inch` (clamped via the `max(min(...))`
  idiom), fit-to-canvas, centered. Watermark, `export_allowed: False`.
- **DXF (shop / CAD):** emit **1:1 model-space geometry in inches** — no
  fit-to-canvas scaling. Use layers (geometry / dimensions / annotation / title
  block) and native dimension entities. Must import cleanly into DraftSight /
  SolidWorks.
- **PDF (submittal):** compose the drawing at a **declared drawing scale** on a
  sheet (paper size + title block standard). Dimension precision per submittal
  spec. `export_allowed` flips to `True` only after the submittal validation gate
  passes.

### Annotation rule

Geometry scales; annotations do not. Dimension text, arrowheads, and
witness-line labels are drawn at **fixed size** (in the SVG/PDF backends),
anchored to datums. Scaling text or arrowheads is a defect.

### Label legibility (Phase 3c — verified against the real EZC-0007)

The narrow spread/end view is the hard case: many dims compete for a ~8" wide
column. The rules that keep it legible — and the precedent for any future view:

- **One view, one job.** The spread/end view carries only what positions the
  circuits: spacing (`S`/`R`), offsets (`I`/`O`), and the box overalls (`CD`/`CH`),
  plus the connection **glyphs** (nozzles, return circles, stubs, tube runs).
  **Per-feature value labels do NOT belong here** — header diameters (`HDx`/`HD`),
  stub length (`SL`), and the `RETURN` connection size are **data-strip / table
  items, deferred to the wider header strip (Phase 4)**. EZC-0007 keeps them out of
  the end view for exactly this reason; forcing them in makes their leaders rake
  through the cramped return column. Keep the glyph, move the text. When a label
  cannot be placed without crossing geometry/another label, **defer it to the right
  view — do not cram it.**
- **Value off its own line.** A dimension value sits a clear gap *beside* its line,
  never on it (strikethrough is a defect). Place it at the **datum end** (away from
  the measured point), like EZC-0007, so it never lands where the dim/ext lines run.
- **Mirror-covariance is load-bearing.** LH↔RH is a single `mirror_view_x` on the
  layer-2 layout, so every placement must be mirror-*covariant*: midpoint `(a+b)/2`
  and `ax + sign(ax-bx)*gap` are; a hardcoded `min(ax,bx)` + fixed anchor is **not**.
  For datum-end text, flip the anchor with the span (`end`↔`start`) so it reflects.
  There are mirror-equivariance tests — run LH and RH for any label change.
- **Obstacle-complete de-collision.** Label nudging treats **dim/witness/leader
  lines + connection glyphs as fixed obstacles**, not just other labels. A green
  label↔label test while lines cross labels is a **false green** — assert
  "no line through any label bbox" and "no glyph over any label bbox" (LH+RH,
  single+multi). Overalls (`kind=="overall"`) draw as tiered **arrows** regardless
  of span; only offsets stay leader-style.

### Phase Gate workflow

- Multi-file changes: **plan first, hold for approval before writing code.**
- A phase closes only when: all tests green **and** an eyeball-verifiable result
  exists.
- Do not advance past a red gate. Do not silently expand scope beyond the
  approved phase.

### Where things live

- Engine (new): `src/coilforge/drawing/schematic_renderer.py`
- Layout/datum module: extracted in Phase 2 — keep it separable from day one.
- Renderer backends: `src/coilforge/drawing/backends/` (`svg.py`, `dxf.py`,
  `pdf.py`).
- Tests: `tests/test_schematic_renderer.py`
- Existing template path — **DO NOT TOUCH**: `slot_population.py::populate_template_slots`,
  the 17 `template.svg` files, `pdf_to_template_drawing.py`.
- Reuse from `phase2a/renderer.py`: the clamp idiom, `REVIEW_WATERMARK`,
  `_esc` / `_text_line` / `_fmt`. Do **not** reuse its x18 / x16 scaling.
  Note: `_conn_float` lives in the frozen `submittal/pdf_to_template_drawing.py`,
  **not** in `renderer.py` — do not import it from that DO-NOT-TOUCH module; the
  engine uses its own `_slot_inches` slot-coercion helper instead.

### Drawing-engine conventions

- Renderers are **pure functions**: input -> result object, no side effects, no
  file writes.
- **Additive only** — no schema changes that would break the upstream confidence
  gate.
- Carry safety flags through: `export_allowed: False` + watermark until the PDF
  submittal path explicitly promotes output to production.

### Test requirements (every change)

- Proportionality: doubling a dimension slot doubles its size within clamps;
  `FL:FH` ratio preserved.
- **Cross-backend dimension parity:** the same coil yields identical real
  dimensions across SVG, DXF, and PDF (only presentation scale differs).
- **DXF 1:1:** geometry emitted in true inches; round-trips at real size.
- **PDF scale:** renders at the declared drawing scale on the chosen sheet.
- One case per category: DX 1/2/3, HGBP, HGRH, CWC, HWC.
- LH <-> RH mirror.
- Missing-slot omission (`None` / "REVIEW REQUIRED" -> omitted + annotated).
- Safety flags asserted (`export_allowed`, watermark present where required).

### Roadmap

1. Engine v0 — geometry model (real units) + DX front view, **SVG** backend +
   tests.
2. Extract layout/datum module; add header/side view (LH/RH mirror).
3. Feature library — all 17 via a `(category, hand, header, special)` spec table.
4. **DXF** backend via `ezdxf` (1:1 inches, layers, dimension entities); verify
   DraftSight / SolidWorks import.
5. **PDF** backend (submittal: title block, declared scale, dimension precision);
   wire the export validation gate that flips `export_allowed`.
6. Integration — wire all three backends into the pipeline + web UI; retire
   template dependency for covered categories.
