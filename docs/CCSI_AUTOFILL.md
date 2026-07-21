# CCSI Online Direct Coil autofill (review aid)

Push CoilForge's 13 resolved **drawing parameters** into the external
**CCSI Online "Direct Coil" DX form** instead of hand-copying them one by one.

This is a **review aid**, not an export. Nothing is written to the CCSI form
without an explicit click, and CoilForge marks every drawing parameter
`review_required` — so the autofill **surfaces** values for you to confirm, it
never silently commits them.

## How it works (clipboard handoff)

CCSI is served over https; browsers block an https page from fetching
`http://localhost`, so CoilForge and the CCSI page can't talk over the network.
Instead the data rides the **clipboard**:

```
CoilForge  ──"Copy CCSI autofill payload"──►  clipboard (JSON)
CCSI form  ──run userscript──►  reads clipboard, fills fields you confirm
```

The userscript is **generic** — it carries no CCSI selectors. Which DOM input
each of the 13 keys maps to comes from a same-origin field map
(`web/ccsi/ccsi_dx_field_map.json`, served at `/static/ccsi/...`). When CCSI
changes its markup, you edit that JSON, not the script.

## Parts

| File | Role |
| --- | --- |
| `web/app.js` (`buildCcsiAutofillPayload`, "Copy CCSI autofill payload" button) | Builds the clipboard payload from the in-memory `DrawingParameterSet`. |
| `web/ccsi/ccsi_dx_field_map.json` | Selector source of truth (CoilForge key → CCSI selectors). Versioned. |
| `web/ccsi/ccsi_autofill.user.js` | Generic clipboard-driven filler (Tampermonkey/Violentmonkey userscript). |
| `tests/test_ccsi_field_map.py` | Guards that the map covers exactly the canonical 13 keys. |

## Payload contract (`coilforge.ccsi.autofill/1`)

```json
{
  "schema": "coilforge.ccsi.autofill/1",
  "generated_at": "<ISO8601>",
  "coil_tag": "CDXC-1",
  "review_aid_only": true,
  "export_allowed": false,
  "form": "CCSI Online Direct Coil — DX",
  "field_map_version": "2026-06-27-stub",
  "fields": [
    {"key":"CD","ccsi_label":"Casing Depth","value":3.5,"unit":"in",
     "status":"review_required","type":"number",
     "selectors":["#casingDepth"],"blocked_reason":null}
  ]
}
```

The userscript **refuses to run** unless `schema` matches and
`review_aid_only:true` / `export_allowed:false`.

### Confidence gate (carried end to end)

- `blocked` / null value → **skipped**, never typed (grey chip + reason).
- `review_required` (all 13 today) → **surfaced**: tick *"I have reviewed these
  review-aid values"*, then **Fill all reviewed** or per-field **Fill**. Amber
  until filled.
- `ready` → reserved one-click path (the resolver emits none for these 13 yet).

## Install & use

**One-time setup (in CoilForge).** Under the Drawing Parameters panel, open
**"CCSI filler — one-time setup"**. Two options:
- **Bookmarklet (no extension):** drag the **CCSI autofill** link to your bookmarks
  bar. CoilForge builds it at runtime from the served userscript (one source of
  truth). Click the bookmark on the CCSI form to open the filler. *Caveat:* if CCSI's
  Content-Security-Policy blocks the bookmarklet, use the userscript option (it runs
  in an isolated world and bypasses page CSP).
- **Userscript manager:** install `/static/ccsi/ccsi_autofill.user.js` into
  Tampermonkey/Violentmonkey, then trigger it from the userscript menu.

**Each use:**
1. In CoilForge, analyze a coil, then click **"Copy CCSI autofill payload"** under the
   Drawing Parameters panel.
2. Switch to the CCSI DX form tab. Trigger the filler (bookmark click, or userscript
   menu → *CoilForge: fill CCSI drawing parameters*). A panel opens.
3. Click **Load from clipboard** (grant the clipboard-read prompt the first time). If
   clipboard read is blocked (e.g. Firefox), paste the JSON into the fallback box and
   click **Load pasted JSON**.
4. Review the listed values, tick the review checkbox, and **Fill**. Each row shows
   ✓ filled, ⚠ mismatch (read-back verified), or skipped (blocked / CCSI read-only).

## Phase 0 — captured (2026-06-28, coil.ccsi.ie/Coils/Edit)

Done. The field map now carries the **real CCSI selectors**. Key finding: 8 of 13
CCSI field ids differ from CoilForge's drawing-param labels — `I→HS`, `S→VS`,
`O→HR`, `R→VR`, `RF→EF`, `HF→FF`, `SL→CS`, `ZD→DX_ZD` (CCSI names them by geometry
role: HS = horizontal-supply, VR = vertical-return, etc.). The form is
**jQuery / server-rendered (ASP.NET MVC + Bootstrap)**, no virtual DOM.

Each `selectors` list tries the real CCSI id first, then falls back to CoilForge's
own mirror (`[data-ccsi-key='<KEY>']`) — so the **same map** works both on the live
CCSI form and the same-origin self-test.

**3 fields are CCSI-computed / `readOnly`** (RF, HF, CH). The userscript detects
`readOnly` and **skips** them (CCSI derives them itself), so their per-field enable
checkmarks correctly stay OFF. CD was reconfirmed editable (2026-07-21) and is now
filled. (The map's `ccsi_readonly` flag is documentary only — the skip is driven by the
live DOM `readOnly` attribute, not the flag.)

**Per-field enable checkmark (auto, 2026-07-21).** On the real CCSI form each editable
dimension `#<id>` has a sibling checkbox `#<id>_isActive` that must be ON for the form to
accept an edit. The filler flips it ON automatically (via a real `.click()`, since the
enable is an inline `onClickDimisActive('<id>')` handler) right before writing the value —
so you no longer tick each one by hand. Fields with no such checkbox (BF/HD/TF/SL/ZD/…)
are always editable. The form-level **Apply Venting and Draining I/O Constraints**
(`#ApplyVDConstraints`) is set ON only for a hot-gas-bypass coil (payload `hot_gas_bypass`)
and OFF for all others. Saving to CCSI is still a manual John-only step.

To re-capture after a CCSI redesign: open the live form, and for each key collect the
on-screen label + an **ordered** selector list (`#id` → `[name=…]` →
`{"strategy":"labelText","text":"…"}` → `{"strategy":"xpath","xpath":"…"}`), then update
`ccsi_dx_field_map.json` and bump `version`.

## Self-test (no CCSI, no network)

1. Run the local app (`run_server.bat`), analyze a coil, click **Copy CCSI autofill
   payload**.
2. On the CoilForge page itself, run the userscript → **Load from clipboard** → the
   stub map resolves against the `#direct-coil-screen-mirror` inputs. Confirm: blocked
   skipped, review_required needs the checkbox, values fill, mismatches flag.

This exercises clipboard read, selector resolution, the gate, the framework-safe
fill (native setter + `input`/`change`/`blur`), and read-back — before touching the
real site.

## Caveats

- **ToS / login:** the userscript only assists a human-driven, already-authenticated
  CCSI session. It handles no credentials and does not automate login. Confirm this
  is acceptable use of the CCSI account.
- **Framework-managed inputs:** values are written via the native setter plus
  synthetic `input`/`change`/`blur` so React/Angular commit them; the read-back check
  flags any field the framework rejects or reformats.
- **Scope:** only the 13 base drawing parameters. Multi-header keys (I2/S2/…) are
  intentionally excluded for v1 — extend the map + the JS key list to add them.
- **Self-test target is cosmetic:** `readonly` does not block a programmatic value
  set, so the mirror fills and reads back ✓ — but the mirror re-renders from state,
  so the write isn't persisted. The self-test proves resolution, gate, fill mechanics,
  and read-back; the persisted-write path is what you verify on the real CCSI form.
