# CoilForge

CoilForge is an internal coil engineering platform concept.

Current scope:
- Phase 1 specification
- DX-only drawing populator MVP planning
- Checklist-to-canonical-to-SVG review-aid workflow

Important:
- This repository should not contain raw customer data, raw EZ Coil PDFs/JSON exports, or manufacturing-approved drawings.
- Generated drawings are review aids only until engineering approval.

## Phase 2A Local Web DX Header 1 MVP

The Phase 2A local MVP is a FastAPI app for the DX Header 1 / EZC-0001
sanitized fixture only. It serves a browser UI for editing the first-slice
parameter state, running validation, rendering an SVG review-aid preview, and
generating checklist snapshot plus drawing metadata objects.

Install local runtime dependencies if they are not already available:

```bash
python -m pip install fastapi uvicorn
```

Start the local server:

```bash
python -m uvicorn coilforge.phase2a.app:app --app-dir src --reload
```

Then open:

```text
http://127.0.0.1:8000
```

Available routes:

- `GET /`
- `GET /api/default-state`
- `POST /api/validate`
- `POST /api/render-svg`
- `POST /api/generate-snapshot`

Compatibility entrypoint:

```bash
python -m uvicorn coilforge.web_app:app --app-dir src --reload
```

Safety boundaries:

- The app uses only `examples/sanitized/dx_header1_ezc0001_default.json`.
- Generated drawings remain `review_aid_only`.
- OAL is displayed as review-required and is not calculated.
