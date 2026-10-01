// ==UserScript==
// @name         CoilForge → CCSI Direct Coil autofill (review aid)
// @namespace    coilforge
// @version      3.1.2
// @description  Bridge the 13 Direct Coil drawing parameters from CoilForge straight into the external CCSI Online DX form — no copy/paste. Runs on both pages; CoilForge "Send to CCSI" pushes via the userscript manager's shared storage, the CCSI tab receives and opens a review-and-fill panel. When filling, it also flips each field's own CCSI "enable" checkmark (<id>_isActive) ON so the form accepts the value, and sets Apply Venting/Draining Constraints ON for hot-gas-bypass coils only. v3: two stages — stage 1 fills the coil data (geometry/options/air/refrigerant/fluid) one field at a time and stops before Calculate; stage 2 fills the drawing parameters once the dimension grid appears. v3.1 adds one button: coil data -> Calculate -> Custom Dimensions -> drawing parameters, then it stops (you press Calculate once more to apply the dimensions, and decide on Save). Review aid only — you confirm every value; read-only fields (RF/HF/CH) are skipped; nothing auto-saves.
// @include      /^https?:\/\/(localhost|127\.0\.0\.1):\d+\//
// @match        https://coil.ccsi.ie/*
// @noframes
// @updateURL    http://localhost:8011/static/ccsi/ccsi_autofill.user.js
// @downloadURL  http://localhost:8011/static/ccsi/ccsi_autofill.user.js
// @grant        GM_setValue
// @grant        GM_getValue
// @grant        GM_addValueChangeListener
// @grant        GM_registerMenuCommand
// @grant        unsafeWindow
// @run-at       document-idle
// ==/UserScript==

/*
 * PORT: the local-server rule is a regex @include (any port on localhost/127.0.0.1),
 * because run_server.bat takes a port argument so several projects can run side by side
 * — a coil open on :8012 must still get the button. @updateURL/@downloadURL cannot be
 * port-agnostic and stay pinned to 8011: auto-update only works while a server is on the
 * default port. The install link in index.html is relative, so installing always works.
 *
 * ONE script, TWO roles (it detects which page it is on):
 *
 *   CoilForge (localhost, any port) — adds a "▶ Send to CCSI" button. On click it reads
 *     the 13 rendered drawing-param values + the field map, builds the payload, and
 *     GM_setValue()s it. No clipboard.
 *   CCSI (coil.ccsi.ie)         — GM_addValueChangeListener wakes on the remote push,
 *     opens the panel and loads the payload. Also a userscript-menu trigger + a
 *     clipboard/paste fallback for when the bridge isn't available (e.g. bookmarklet).
 *
 * Confidence gate carried end to end: blocked/no-value -> skipped; review_required ->
 * confirm-before-fill; CCSI read-only fields (CD/RF/HF/CH) -> skipped. Framework-safe
 * fill (native setter + input/change/blur) with read-back verify.
 */
(function () {
  "use strict";

  const SCHEMA = "coilforge.ccsi.autofill/1";
  // Shown in the panel header so you can SEE which filler version is actually running —
  // a stale bookmarklet / old Tampermonkey install is invisible otherwise. Keep in sync
  // with @version above.
  const SCRIPT_VERSION = "3.1.2";
  // Must equal web/app.js::CCSI_WATER_DRAIN_VENT_LOCATION (pinned by a test). Every CWC/HWC,
  // all product lines (John 2026-09-23).
  const WATER_DRAIN_VENT_LOCATION = "Hdr Side In Airflow Dir.";
  const BRIDGE_KEY = "coilforge_ccsi_payload";
  const PANEL_ID = "coilforge-ccsi-autofill-panel";
  const STALE_MS = 10 * 60 * 1000;

  // The CoilForge page is identified by its own markup, not by "is localhost". The
  // @include above is deliberately every port on localhost (see PORT note), so the
  // hostname says nothing: any other local tool — the BTO Ordering Tool on :8501, say —
  // matched too and got a "Send to CCSI" button that belongs to a different app.
  // #drawing-parameters is static in web/index.html (an empty div the app fills later),
  // so it is present at document-idle and needs no retry.
  const onCoilForge = !!document.querySelector("#drawing-parameters");
  const onCcsi = location.hostname.endsWith("ccsi.ie");

  // Top-level page only. Tampermonkey injects into every matching frame, and CCSI's
  // "Coil Drawing" viewer is an embedded same-origin iframe — without this the bridge
  // listener wakes in that frame too and opens a duplicate, empty panel over the drawing.
  // @noframes (header) covers the userscript-manager path; this guards every other one.
  if (window.self !== window.top) {
    return;
  }

  // Bookmarklet/menu entry point (CCSI side).
  window.coilforgeCcsiAutofill = openPanel;

  if (onCoilForge) {
    addSendButton();
  }
  if (onCcsi) {
    if (typeof GM_registerMenuCommand === "function") {
      GM_registerMenuCommand("CoilForge: fill CCSI drawing parameters", openPanel);
    }
    if (typeof GM_addValueChangeListener === "function") {
      GM_addValueChangeListener(BRIDGE_KEY, (_name, _old, newValue, remote) => {
        if (!remote) {
          return; // ignore our own writes
        }
        try {
          const env = JSON.parse(newValue);
          openPanel();
          load(env.payload);
        } catch (e) {
          /* ignore malformed push */
        }
      });
    }
  }

  // ===================== CoilForge side: Send to CCSI =====================
  function addSendButton() {
    if (document.getElementById("coilforge-send-ccsi")) {
      return;
    }
    const b = btn("▶ Send to CCSI", onSend, {
      position: "fixed", right: "16px", bottom: "16px", zIndex: "2147483647",
      padding: "9px 14px", background: "#2563eb", color: "#fff",
      border: "1px solid #1d4ed8", borderRadius: "6px", fontWeight: "600",
      boxShadow: "0 4px 14px rgba(0,0,0,.25)",
    });
    b.id = "coilforge-send-ccsi";
    b.title = "Push the 13 drawing parameters to the open CCSI form (review aid)";
    document.body.append(b);
  }

  async function onSend() {
    try {
      const payload = await buildPayloadFromDom();
      if (!payload.fields.some((f) => f.value !== null)) {
        toast("Analyze a coil first — no drawing values to send yet.", true);
        return;
      }
      if (typeof GM_setValue !== "function") {
        toast("Run this as a userscript (Tampermonkey), not a bookmarklet, to use Send.", true);
        return;
      }
      GM_setValue(BRIDGE_KEY, JSON.stringify({ payload, ts: Date.now() }));
      const n = payload.fields.filter((f) => f.value !== null).length;
      toast(`Sent ${n} values to the CCSI tab — switch there to review & fill.`);
    } catch (e) {
      toast(`Send failed: ${e}`, true);
    }
  }

  async function buildPayloadFromDom() {
    const map = await fetch("/static/ccsi/ccsi_dx_field_map.json", { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : Promise.reject(r.status)));
    const dom = {};
    document.querySelectorAll("#drawing-parameters [data-drawing-param]").forEach((inp) => {
      dom[inp.dataset.drawingParam] = inp.value;
    });
    // Mirror of web/app.js::CCSI_WATER_NO_ZD — CCSI's water-coil grid has no ZD field.
    const category = String(document.querySelector("#drawing-parameters")?.dataset.coilCategory || "").toUpperCase();
    const isWater = category === "CWC" || category === "HWC";
    const fields = Object.keys(map.fields).map((key) => {
      const raw = dom[key];
      const has = raw !== undefined && raw !== "" && raw !== null;
      const num = Number(raw);
      const entry = map.fields[key] || {};
      const noCcsiTarget = isWater && /^ZD\d*$/.test(key);
      return {
        key,
        ccsi_label: entry.ccsi_label || key,
        value: has ? (Number.isFinite(num) ? num : raw) : null,
        unit: entry.unit || "in",
        status: has && !noCcsiTarget ? "review_required" : "blocked",
        type: entry.type || "number",
        ccsi_readonly: entry.ccsi_readonly === true,
        selectors: Array.isArray(entry.selectors) ? entry.selectors : [],
        blocked_reason: noCcsiTarget
          ? "CCSI water-coil dimension grid has no ZD field — not pushed."
          : has ? null : "No value derived from the source or rule engine; review required.",
      };
    });
    return {
      schema: SCHEMA,
      generated_at: new Date().toISOString(),
      coil_tag: (document.querySelector("#edit-coil-name") || {}).value || null,
      review_aid_only: true,
      export_allowed: false,
      form: map.form || "CCSI Online Direct Coil — DX",
      field_map_version: map.version || "unknown",
      // HGBP rides along so the CCSI side can set Apply Venting/Draining Constraints. On this
      // DOM-scraped bridge path CoilForge stamps it onto #drawing-parameters at render time.
      hot_gas_bypass: document.querySelector("#drawing-parameters")?.dataset.specialFeature === "HGBP",
      // Same stamp mechanism for the coil category: water coils get the Drain and Vent
      // Location select (see drainVentLocationEntry).
      drain_vent_location: drainVentLocationEntry(
        document.querySelector("#drawing-parameters")?.dataset.coilCategory,
      ),
      // Stage 1 (Rating mode): CoilForge stamps /api/ccsi/coil-data-payload's block here.
      coil_data: readCoilData(),
      fields,
    };
  }

  function toast(message, warn) {
    const t = el("div", { textContent: message }, {
      position: "fixed", right: "16px", bottom: "62px", zIndex: "2147483647",
      maxWidth: "320px", padding: "8px 12px", borderRadius: "6px",
      font: "12px/1.4 system-ui, sans-serif",
      background: warn ? "#fdeceb" : "#e8f5ec",
      color: warn ? "#b3261e" : "#1a7f37",
      border: `1px solid ${warn ? "#f3c2bd" : "#bfe3cb"}`,
    });
    document.body.append(t);
    setTimeout(() => t.remove(), 4000);
  }

  // ===================== CCSI side: review & fill panel =====================
  function openPanel() {
    document.getElementById(PANEL_ID)?.remove();
    const panel = el("div", { id: PANEL_ID }, {
      position: "fixed", top: "16px", right: "16px", zIndex: "2147483647",
      width: "420px", maxHeight: "85vh", overflowY: "auto", background: "#fff",
      color: "#1c2430", border: "1px solid #c4ccd6", borderRadius: "8px",
      boxShadow: "0 8px 30px rgba(0,0,0,.25)", font: "13px/1.4 system-ui, sans-serif",
      padding: "12px",
    });
    panel.append(
      header(),
      note("Review aid only — not a final Direct Coil export. You confirm every value."),
      sourceRow(),
      loadControls(),
      el("div", { id: "ccsi-af-body" }),
    );
    document.body.append(panel);
  }

  function header() {
    const bar = el("div", {}, { display: "flex", justifyContent: "space-between", alignItems: "center" });
    bar.append(
      el("strong", { textContent: `CoilForge → CCSI autofill v${SCRIPT_VERSION}` }),
      btn("✕", () => document.getElementById(PANEL_ID)?.remove(), { border: "none", background: "transparent", fontSize: "16px" }),
    );
    return bar;
  }

  function sourceRow() {
    return el("div", { id: "ccsi-af-source", textContent: "Waiting for a push from CoilForge (or load manually below)." },
      { margin: "8px 0", fontSize: "12px", color: "#5a6573" });
  }

  function loadControls() {
    const wrap = el("div", {}, { display: "grid", gap: "6px", margin: "8px 0" });
    const ta = el("textarea", { id: "ccsi-af-paste", placeholder: "Fallback: paste the CoilForge payload JSON here, then click “Load pasted JSON”." },
      { width: "100%", height: "44px", fontFamily: "monospace", fontSize: "11px" });
    const row = el("div", {}, { display: "flex", gap: "6px" });
    row.append(
      btn("Load from clipboard", onLoadClipboard),
      btn("Load pasted JSON", () => load(ta.value)),
    );
    wrap.append(row, ta);
    return wrap;
  }

  async function onLoadClipboard() {
    let text = "";
    try {
      if (navigator.clipboard?.readText) {
        text = await navigator.clipboard.readText();
      } else {
        throw new Error("clipboard read unavailable");
      }
    } catch (e) {
      setSource(`Clipboard read failed (${e.message}). Use the paste fallback below.`, true);
      return;
    }
    load(text);
  }

  // Accepts a JSON string OR an already-parsed payload object (bridge push).
  function load(input) {
    let payload;
    if (typeof input === "string") {
      try {
        payload = JSON.parse(input);
      } catch {
        setSource("Could not parse JSON — is the CoilForge payload present?", true);
        return;
      }
    } else {
      payload = input;
    }
    if (!payload || payload.schema !== SCHEMA) {
      setSource(`Unexpected schema (${payload && payload.schema || "none"}). Expected ${SCHEMA}.`, true);
      return;
    }
    if (payload.review_aid_only !== true || payload.export_allowed !== false) {
      setSource("Refusing to run: payload is not flagged review_aid_only / export_allowed:false.", true);
      return;
    }
    const ageMs = payload.generated_at ? Date.now() - Date.parse(payload.generated_at) : NaN;
    const stale = Number.isFinite(ageMs) && ageMs > STALE_MS;
    setSource(
      `Coil ${payload.coil_tag || "—"} · ${payload.form || ""} · map v${payload.field_map_version || "?"}` +
      (stale ? "  ⚠ payload is >10 min old — re-send from CoilForge if the coil changed." : ""),
      stale,
    );
    renderFields(payload);
  }

  function renderFields(payload) {
    const body = document.getElementById("ccsi-af-body");
    body.innerHTML = "";

    const gate = el("label", {}, { display: "flex", gap: "6px", alignItems: "center", margin: "6px 0" });
    const gateCheck = el("input", { type: "checkbox" });
    gate.append(gateCheck, el("span", { textContent: "I have reviewed these review-aid values" }));

    const fillAll = btn("Stage 2 — fill drawing parameters", () => {
      entriesOf(payload).forEach((f) => { if (isFillable(f)) fillOne(f); });
      applyFormLevelToggles(payload);
      summarize(payload);
    });
    fillAll.disabled = true;
    gateCheck.addEventListener("change", () => { fillAll.disabled = !gateCheck.checked; });

    body.append(
      gate,
      runAllSection(payload, gateCheck),
      coilDataSection(payload, gateCheck),
      el("div", { id: "ccsi-af-stage2" }, { margin: "6px 0 2px", fontSize: "12px", color: "#5a6573" }),
      fillAll,
      el("div", { id: "ccsi-af-summary" }, { margin: "6px 0", fontSize: "12px" }),
    );

    entriesOf(payload).forEach((field) => {
      const resolved = resolve(field.selectors);
      const row = el("div", { id: rowId(field.key) },
        { display: "grid", gridTemplateColumns: "44px 1fr auto", gap: "6px", alignItems: "center",
          padding: "4px 0", borderTop: "1px solid #eef1f4" });
      const label = el("div", {}, { fontSize: "12px" });
      label.append(el("strong", { textContent: field.key }),
        el("div", { textContent: field.ccsi_label || "" }, { color: "#5a6573", fontSize: "11px" }));
      const mid = el("div", {});
      mid.append(chip(field, resolved));
      const action = el("div", {});
      if (isFillable(field)) {
        const b = btn("Fill", () => { fillOne(field); applyFormLevelToggles(payload); summarize(payload); });
        b.disabled = !resolved || field.ccsi_readonly;
        action.append(b);
      }
      row.append(label, mid, action);
      body.append(row);
    });
    summarize(payload);
    watchDimensionGrid(payload);
  }

  // ===================== Stage 1: coil data (Rating mode) =====================
  // The coil_data block is CoilForge's /api/ccsi/coil-data-payload output; only `pushable`
  // entries (validated mappings + the approved default profile) are written. CCSI refreshes
  // dependent dropdowns on every change (getDependencyOptions -> /Coils/GetDependencies), so
  // fields go ONE AT A TIME in form order, each waiting for the page's AJAX to settle, and all
  // are re-verified at the end: a later dependency refresh can reset an earlier select.
  // This stage never presses Calculate — the engineer does, after reviewing.
  function readCoilData() {
    const raw = document.querySelector("#drawing-parameters")?.dataset.ccsiCoilData;
    if (!raw) return null;
    try { return JSON.parse(raw); } catch { return null; }
  }

  function pageWindow() {
    return typeof unsafeWindow !== "undefined" ? unsafeWindow : window;
  }

  function ajaxIdle(timeoutMs = 8000) {
    const start = Date.now();
    return new Promise((done) => {
      const tick = () => {
        const jq = pageWindow().jQuery;
        if (!jq || jq.active === 0 || Date.now() - start > timeoutMs) { done(); return; }
        setTimeout(tick, 80);
      };
      setTimeout(tick, 60);
    });
  }

  function coilDataTargets(block) {
    return (block.entries || []).filter((e) => e.pushable && e.value !== null && e.value !== undefined);
  }

  // CCSI re-renders a dependent select after getDependencyOptions, and the re-rendered option
  // TEXT can differ from the first render: live 2026-09-30, Tube Material "Copper 0.016 Plain"
  // came back as "Copper - 0.016 Plain" (which is also its option VALUE) once Tube Diameter
  // changed. So a coil-data option matches on text OR value, with the " - " separator ignored.
  function coilOptionKey(text) {
    return normOptionText(text).replace(/\s+-\s+/g, " ");
  }

  function optionForCoilData(select, text) {
    const want = coilOptionKey(text);
    return [...select.options].find((o) => coilOptionKey(o.textContent) === want || coilOptionKey(o.value) === want) || null;
  }

  function writeCoilDataEntry(target, entry) {
    if (target instanceof HTMLSelectElement) {
      const option = optionForCoilData(target, entry.value);
      if (!option) return "no_option";
      setNativeValue(target, option.value);
    } else {
      setNativeValue(target, entry.value);
    }
    ["input", "change", "blur"].forEach((type) => target.dispatchEvent(new Event(type, { bubbles: true })));
    return "written";
  }

  function coilDataMatches(target, entry) {
    if (target instanceof HTMLSelectElement) {
      const selected = target.options[target.selectedIndex];
      const want = coilOptionKey(entry.value);
      return !!selected && (coilOptionKey(selected.textContent) === want || coilOptionKey(selected.value) === want);
    }
    const got = String(target.value).trim();
    const a = Number(got), b = Number(entry.value);
    return got === String(entry.value).trim() || (Number.isFinite(a) && Number.isFinite(b) && Math.abs(a - b) < 1e-9);
  }

  async function fillCoilDataStage(block, out) {
    const targets = coilDataTargets(block);
    const results = [];
    for (const entry of targets) {
      const target = document.querySelector(entry.selector);
      if (!target) { results.push([entry, "not_on_form"]); continue; }
      // Read-only here is CCSI's own lock (Altitude under Standard air, for one) — skip, never force.
      if (target.readOnly || target.disabled) { results.push([entry, "locked"]); continue; }
      const r = writeCoilDataEntry(target, entry);
      results.push([entry, r]);
      out.textContent = `Stage 1: ${results.length} / ${targets.length} …`;
      if (r === "written") await ajaxIdle();
    }
    await ajaxIdle();
    return results.map(([entry, r]) => {
      const target = document.querySelector(entry.selector);
      const ok = r === "written" && !!target && coilDataMatches(target, entry);
      return { entry, status: r === "written" ? (ok ? "ok" : "reset_or_mismatch") : r };
    });
  }

  function coilDataSection(payload, gateCheck) {
    const block = payload.coil_data;
    const wrap = el("div", { id: "ccsi-af-coildata" },
      { margin: "8px 0", padding: "8px", border: "1px solid #dbe2ea", borderRadius: "6px" });
    if (!block || !Array.isArray(block.entries)) {
      wrap.append(note("Stage 1 — no coil data in this payload (drawing parameters only)."));
      return wrap;
    }
    const targets = coilDataTargets(block);
    const held = block.entries.length - targets.length;
    wrap.append(el("strong", { textContent: `Stage 1 — coil data (${block.coil_type || "?"}: ${targets.length} to fill, ${held} held)` }));
    if (block.geometry_reselect_reason) {
      wrap.append(note(`Rows / FPI / fin withheld — re-select them in CCSI: ${block.geometry_reselect_reason}`));
    }
    const out = el("div", {}, { fontSize: "12px", margin: "4px 0" });
    const go = btn("Stage 1 — fill coil data (stops before Calculate)", async () => {
      go.disabled = true;
      const res = await fillCoilDataStage(block, out);
      const bad = res.filter((r) => r.status !== "ok");
      out.textContent = `Stage 1 done: ${res.length - bad.length}/${res.length} set` +
        (bad.length ? ` · ⚠ ${bad.map((r) => `${r.entry.ccsi_id}: ${r.status}`).join(", ")}` : "") +
        " — review, then press Calculate in CCSI yourself.";
      out.style.color = bad.length ? "#b3261e" : "#1a7f37";
      go.disabled = !gateCheck.checked;
    });
    go.disabled = !gateCheck.checked;
    gateCheck.addEventListener("change", () => { go.disabled = !gateCheck.checked; });
    wrap.append(go, out);
    return wrap;
  }

  // ===================== One button (v3.1) =====================
  // coil data -> Calculate -> Custom Dimensions -> drawing parameters, then STOP. The engineer
  // presses Calculate once more (with the grid open calculateCoilData calls customDimensionsApply,
  // which applies the dimensions and re-rates) and decides on Save. Exactly two CCSI buttons are
  // pressed here — #calcBtn and #customDimensionsButton — never Save / Save & Continue / Drawing /
  // TechSpec / Cancel. Arrival is detected with a hidden marker dropped into the area CCSI replaces:
  // an identical re-calculation can return byte-identical HTML, so "content changed" is not enough.
  // The marker is a <span>, not a form control, so convertFormToJSON never sends it.
  function visible(node) {
    return !!node && node.getBoundingClientRect().width > 0;
  }

  function waitFor(predicate, timeoutMs, label) {
    const start = Date.now();
    return new Promise((done, fail) => {
      const tick = () => {
        let ok = false;
        try { ok = !!predicate(); } catch { ok = false; }
        if (ok) { done(); return; }
        if (Date.now() - start > timeoutMs) { fail(new Error(`timed out waiting for ${label}`)); return; }
        setTimeout(tick, 250);
      };
      tick();
    });
  }

  function dropMarker(containerId, markerId) {
    const container = document.getElementById(containerId);
    if (!container) return;
    document.getElementById(markerId)?.remove();
    container.append(el("span", { id: markerId }, { display: "none" }));
  }

  async function runAll(payload, out) {
    const say = (text, bad) => { out.textContent = text; out.style.color = bad ? "#b3261e" : "#1c2430"; };
    // No coil data = nothing to rate: calculating now would rate whatever the CCSI form already
    // holds (a stale or half-copied payload). Stop instead; stage 2 alone stays available below.
    if (!payload.coil_data || !Array.isArray(payload.coil_data.entries) || !coilDataTargets(payload.coil_data).length) {
      say("Stopped: this payload has no coil data, so nothing was calculated. Re-copy the payload from CoilForge (wait for the drawing panel to finish loading).", true);
      return;
    }
    {
      say("1/4 — filling coil data …");
      const res = await fillCoilDataStage(payload.coil_data, out);
      const bad = res.filter((r) => r.status !== "ok" && r.status !== "locked");
      if (bad.length) {
        say(`Stopped after coil data (nothing calculated): ${bad.map((r) => `${r.entry.ccsi_id}: ${r.status}`).join(", ")}`, true);
        return;
      }
    }
    const calcButton = document.getElementById("calcBtn");
    if (!calcButton) { say("Stopped: CCSI Calculate button not found.", true); return; }
    say("2/4 — Calculate …");
    dropMarker("mainResult", "cf-calc-marker");
    calcButton.click();
    // #mainResult itself is NOT tested for visibility: with the dimension grid open CCSI keeps the
    // result block display:none (live 2026-09-30), so arrival = marker gone + result buttons shown.
    await waitFor(() => !document.getElementById("cf-calc-marker")
      && visible(document.getElementById("customDimensionsButton")), 60000, "the Calculate result");
    await ajaxIdle(20000);
    const cdButton = document.getElementById("customDimensionsButton");
    say("3/4 — Custom Dimensions …");
    dropMarker("cdFormId", "cf-grid-marker");
    cdButton.click();
    const probe = (payload.fields || []).map((f) => f.selectors).find((sel) => Array.isArray(sel) && sel.length);
    await waitFor(() => {
      const grid = document.getElementById("cdFormId");
      const target = probe ? resolve(probe) : null;
      return !!grid && !document.getElementById("cf-grid-marker") && !!target && grid.contains(target) && visible(target);
    }, 60000, "the dimension grid");
    await ajaxIdle(20000);
    say("4/4 — drawing parameters …");
    const entries = entriesOf(payload).filter((f) => isFillable(f));
    entries.forEach((f) => fillOne(f));
    applyFormLevelToggles(payload);
    summarize(payload);
    const written = entries.filter((f) => !f.ccsi_readonly);
    const off = written.filter((f) => { const t = resolve(f.selectors); return !t || !verify(t, f); });
    say(`Done: coil data set, calculated, ${written.length - off.length}/${written.length} drawing parameters set` +
      (off.length ? ` (⚠ ${off.map((f) => f.key).join(", ")})` : "") +
      ". Nothing was saved — review, press Calculate to apply the dimensions, then Save if right.", off.length > 0);
  }

  function runAllSection(payload, gateCheck) {
    const wrap = el("div", { id: "ccsi-af-runall" },
      { margin: "8px 0", padding: "8px", border: "1px solid #bcd3f5", borderRadius: "6px", background: "#f5f9ff" });
    const out = el("div", { id: "ccsi-af-runall-out" }, { fontSize: "12px", margin: "4px 0" });
    const go = btn("▶ Run all — coil data → Calculate → drawing parameters (stops before Save)", async () => {
      go.disabled = true;
      try {
        await runAll(payload, out);
      } catch (e) {
        out.textContent = `Stopped: ${e.message}. Nothing was saved.`;
        out.style.color = "#b3261e";
      } finally {
        go.disabled = !gateCheck.checked;
      }
    }, { fontWeight: "600" });
    go.id = "ccsi-af-runall-btn";
    go.disabled = !gateCheck.checked;
    gateCheck.addEventListener("change", () => { go.disabled = !gateCheck.checked; });
    wrap.append(go, out);
    return wrap;
  }

  // Stage 2 (drawing parameters) needs CCSI's dimension grid, which renders only after the
  // engineer's own Calculate -> Custom Dimensions. Watch for it instead of guessing.
  function watchDimensionGrid(payload) {
    const probe = (payload.fields || []).map((f) => f.selectors).find((sel) => Array.isArray(sel) && sel.length);
    const present = () => !!probe && !!resolve(probe);
    const update = () => {
      const hint = document.getElementById("ccsi-af-stage2");
      if (hint) {
        hint.textContent = present()
          ? "Stage 2 — dimension grid found: fill the drawing parameters."
          : "Stage 2 — waiting for the dimension grid (press Calculate → Custom Dimensions in CCSI).";
      }
    };
    update();
    if (present()) return;
    const obs = new MutationObserver(() => {
      if (present()) { obs.disconnect(); update(); summarize(payload); }
    });
    obs.observe(document.body, { childList: true, subtree: true });
  }

  function chip(field, resolved) {
    let text, color;
    if (!resolved && isFillable(field)) {
      text = "selector not found"; color = "#b3261e";
    } else if (field.selector_verified === false && isFillable(field)) {
      // No Phase-0 capture for this field — it resolved by label text, which is an inference.
      // Say so loudly and show what it landed on, so John confirms the target before writing.
      text = `⚠ UNVERIFIED target <${resolved.tagName.toLowerCase()}${resolved.id ? "#" + resolved.id : ""}> — confirm, then: ${field.value}`;
      color = "#b3261e";
    } else if (field.ccsi_readonly && isFillable(field)) {
      text = `CCSI read-only (computed) — skipped, was ${resolved ? resolved.value : ""}`; color = "#6b7280";
    } else if (field.status === "blocked" || field.value === null || field.value === undefined) {
      text = `skipped — ${field.blocked_reason || "no value"}`; color = "#6b7280";
    } else if (field.status === "review_required") {
      text = `review: ${field.value}${field.unit ? " " + field.unit : ""}`; color = "#9a6700";
    } else {
      text = `${field.value}`; color = "#1a7f37";
    }
    return el("span", { textContent: text }, { color, fontSize: "12px", display: "inline-block", maxWidth: "230px" });
  }

  // Everything the panel offers to fill: the 13 (+multi-header) dimensions, plus the
  // engine-assembled Drawing Notes if CoilForge sent any. Notes ride the payload as a
  // SEPARATE top-level key, never inside `fields` — that array is contract-tested to hold
  // only dimension keys (they carry a unit and a captured CCSI #id; a text note has neither).
  // Adapting it here keeps the contract intact while the UI treats every row the same way.
  function entriesOf(payload) {
    const entries = [...payload.fields];
    const notes = payload.drawing_notes;
    if (notes && notes.value !== null && notes.value !== undefined && notes.value !== "") {
      entries.push({ ...notes, key: "NOTES", ccsi_readonly: false, unit: null });
    }
    // CCSI "Drain and Vent Location" (water coils only; null otherwise). Same adapter shape.
    const dvl = payload.drain_vent_location;
    if (dvl && dvl.value !== null && dvl.value !== undefined && dvl.value !== "") {
      entries.push({ ...dvl, key: "DVL", ccsi_readonly: false, unit: null });
    }
    return entries;
  }

  // Mirror of web/app.js::ccsiDrainVentLocation for the DOM-scraped bridge path.
  function drainVentLocationEntry(coilCategory) {
    const category = String(coilCategory || "").toUpperCase();
    if (category !== "CWC" && category !== "HWC") return null;
    return {
      ccsi_label: "Drain and Vent Location",
      value: WATER_DRAIN_VENT_LOCATION,
      status: "review_required",
      type: "select",
      match: "option_text",
      // `#DrainAndVentLocation` captured live 2026-10-01; labelText alone resolved to nothing.
      selectors: [
        { strategy: "css", selector: "#DrainAndVentLocation" },
        { strategy: "labelText", text: "Drain and Vent Location" },
      ],
      selector_verified: true,
      blocked_reason: null,
    };
  }

  function isFillable(field) {
    return field.value !== null && field.value !== undefined && field.status !== "blocked";
  }

  function resolve(selectors) {
    if (!Array.isArray(selectors)) return null;
    for (const sel of selectors) {
      let found = null;
      try {
        if (typeof sel === "string") {
          found = document.querySelector(sel);
        } else if (sel && sel.strategy === "css" && sel.selector) {
          // The object form of a CSS selector. It was never handled here, so the live-captured
          // `#DrawingNotes` entry resolved to nothing and the notes fell through to label text
          // — which CCSI's own markup defeats (`for="Drawing_Notes"` names a missing id).
          found = document.querySelector(sel.selector);
        } else if (sel && sel.strategy === "labelText" && sel.text) {
          found = byLabelText(sel.text);
        } else if (sel && sel.strategy === "xpath" && sel.xpath) {
          const r = document.evaluate(sel.xpath, document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null);
          found = r.singleNodeValue;
        }
      } catch {
        found = null;
      }
      if (found) return found;
    }
    return null;
  }

  function byLabelText(text) {
    const needle = text.trim().toLowerCase();
    for (const lbl of document.querySelectorAll("label")) {
      if (!lbl.textContent.trim().toLowerCase().includes(needle)) continue;
      if (lbl.htmlFor) {
        const target = document.getElementById(lbl.htmlFor);
        if (target) return target;
      }
      const inner = lbl.querySelector("input, select, textarea");
      if (inner) return inner;
    }
    return null;
  }

  function fillOne(field) {
    const target = resolve(field.selectors);
    if (!target) return;
    // RF/HF/CH are CCSI-computed: leave their enable checkmark OFF and never write them.
    // The skip is keyed on the MAP flag (field.ccsi_readonly), NOT the live DOM readOnly —
    // on the real CCSI form EVERY editable dimension's input is readOnly until its own
    // <id>_isActive checkmark is ticked, so a live-readOnly test here would wrongly skip the
    // very fields we must fill.
    if (field.ccsi_readonly) { markRow(field, "readonly"); return; }
    // Enable the field's own <id>_isActive checkmark FIRST — ticking it is what clears the
    // input's readOnly and makes CCSI accept the value — then write + read-back verify.
    enableFieldForUpdate(target);
    if (target.readOnly) { markRow(field, "readonly"); return; }
    // A select filled by OPTION TEXT: CCSI's option values are its own codes, so the value
    // written is whatever the option labelled `field.value` carries. No matching option ->
    // nothing is written (never a guessed code) and the row says so.
    if (target instanceof HTMLSelectElement && field.match === "option_text") {
      const option = optionByText(target, field.value);
      if (!option) {
        markRow(field, "mismatch");
        toast(`"${field.value}" is not an option of ${field.ccsi_label || field.key} — left unchanged.`, true);
        return;
      }
      setNativeValue(target, option.value);
      ["input", "change", "blur"].forEach((type) => target.dispatchEvent(new Event(type, { bubbles: true })));
      markRow(field, verify(target, field) ? "ok" : "mismatch");
      return;
    }
    // Write the SAME normalization verify() will compare against (see forTarget): writing
    // the raw multi-line value and comparing the collapsed one would report a mismatch on
    // every successful notes fill.
    setNativeValue(target, forTarget(target, field.value));
    ["input", "change", "blur"].forEach((type) => target.dispatchEvent(new Event(type, { bubbles: true })));
    markRow(field, verify(target, field) ? "ok" : "mismatch");
  }

  // Turn on the field's own CCSI "<id>_isActive" enable checkbox. Ticking it fires the inline
  // onclick (onClickDimisActive('<id>')) which ALSO clears the input's readOnly, so a bare
  // .checked=true would not work — dispatch a real .click(), and only when it is currently off
  // so an already-enabled field is never toggled back off. Fields with no such checkbox
  // (BF/HD/TF/SL/ZD/HD2..) are always editable; RF/HF/CH are skipped upstream by ccsi_readonly.
  function enableFieldForUpdate(target) {
    const active = target.id ? document.getElementById(`${target.id}_isActive`) : null;
    if (active && !active.disabled && !active.checked) {
      active.click();
    }
  }

  // Form-level toggle applied once per fill run: "Apply Venting and Draining I/O
  // Constraints" (#ApplyVDConstraints) must be ON only for a hot-gas-bypass coil and OFF
  // for every other one. It is a plain checkbox (no CCSI handler), so a direct set + change
  // is enough; idempotent and null-guarded (absent on the localhost self-test mirror).
  function applyFormLevelToggles(payload) {
    const vd = document.getElementById("ApplyVDConstraints");
    if (!vd) return;
    const want = payload.hot_gas_bypass === true;
    if (vd.checked !== want) {
      vd.checked = want;
      vd.dispatchEvent(new Event("change", { bubbles: true }));
    }
  }

  function setNativeValue(target, value) {
    const proto = target instanceof HTMLTextAreaElement
      ? HTMLTextAreaElement.prototype
      : target instanceof HTMLSelectElement
        ? HTMLSelectElement.prototype
        : HTMLInputElement.prototype;
    const setter = Object.getOwnPropertyDescriptor(proto, "value")?.set;
    if (setter) {
      setter.call(target, String(value));
    } else {
      target.value = String(value);
    }
  }

  // A single-line <input> silently drops newlines, so a multi-line value can never read
  // back as it was written. CCSI's Drawing Notes is exactly that (`#DrawingNotes` is an
  // <input type=text>, captured live 2026-08-05) and CoilForge assembles its notes one per
  // line. Collapse newlines to "; " for such a target -- and apply the SAME collapse to
  // BOTH sides in verify(), or the fill succeeds and still reports a mismatch forever.
  // A <textarea> keeps the original text untouched.
  function forTarget(target, value) {
    const text = String(value);
    if (target instanceof HTMLTextAreaElement) return text;
    return text.replace(/\s*\n+\s*/g, "; ").trim();
  }

  // Option text compared loosely: whitespace collapsed, case-insensitive, a trailing period
  // optional ("Hdr Side In Airflow Dir." vs "Hdr Side In Airflow Dir").
  function normOptionText(text) {
    return String(text || "").replace(/\s+/g, " ").trim().replace(/\.$/, "").toLowerCase();
  }

  function optionByText(select, text) {
    const want = normOptionText(text);
    return [...select.options].find((o) => normOptionText(o.textContent) === want) || null;
  }

  function verify(target, field) {
    if (target instanceof HTMLSelectElement && field.match === "option_text") {
      const selected = target.options[target.selectedIndex];
      return !!selected && normOptionText(selected.textContent) === normOptionText(field.value);
    }
    const got = String(target.value).trim();
    if (got === forTarget(target, field.value).trim()) return true;
    const a = Number(got), b = Number(field.value);
    return Number.isFinite(a) && Number.isFinite(b) && a === b;
  }

  function markRow(field, kind) {
    const row = document.getElementById(rowId(field.key));
    if (!row) return;
    const bg = { ok: "#e8f5ec", mismatch: "#fdeceb", readonly: "#f1f3f5" };
    const lab = { ok: "✓ filled", mismatch: "⚠ mismatch — check the field", readonly: "skipped — CCSI read-only" };
    const fg = { ok: "#1a7f37", mismatch: "#b3261e", readonly: "#6b7280" };
    row.style.background = bg[kind] || "#fff";
    const mid = row.children[1];
    if (mid) {
      mid.innerHTML = "";
      mid.append(el("span", { textContent: lab[kind] || "" }, { color: fg[kind] || "#1c2430", fontSize: "12px" }));
    }
  }

  function summarize(payload) {
    const out = document.getElementById("ccsi-af-summary");
    if (!out) return;
    const entries = entriesOf(payload);
    const rows = entries.map((f) => ({ f, t: resolve(f.selectors) }));
    const writable = rows.filter(({ f, t }) => isFillable(f) && t && !f.ccsi_readonly);
    const filled = writable.filter(({ f, t }) => verify(t, f) && String(t.value).trim() !== "").length;
    const readOnly = rows.filter(({ f, t }) => isFillable(f) && t && f.ccsi_readonly).length;
    const notFound = rows.filter(({ f, t }) => isFillable(f) && !t).length;
    const unverified = rows.filter(({ f, t }) => isFillable(f) && t && f.selector_verified === false).length;
    const skipped = entries.filter((f) => !isFillable(f)).length + readOnly;
    out.textContent =
      `${filled}/${writable.length} filled · ${skipped} skipped (blocked/no value/read-only)` +
      (notFound ? ` · ${notFound} selector(s) not found` : "") +
      (unverified ? ` · ⚠ ${unverified} unverified target(s) — confirm before filling` : "");
  }

  // ===================== shared DOM helpers =====================
  function rowId(key) { return `ccsi-af-row-${key}`; }

  function setSource(text, warn) {
    const node = document.getElementById("ccsi-af-source");
    if (!node) return;
    node.textContent = text;
    node.style.color = warn ? "#b3261e" : "#5a6573";
  }

  function note(text) {
    return el("div", { textContent: text },
      { fontSize: "11px", color: "#9a6700", background: "#fff8e6", border: "1px solid #f0e0a8",
        borderRadius: "4px", padding: "4px 6px", margin: "6px 0" });
  }

  function el(tag, props, style) {
    const node = document.createElement(tag);
    if (props) Object.assign(node, props);
    if (style) Object.assign(node.style, style);
    return node;
  }

  function btn(text, onClick, style) {
    const b = el("button", { type: "button", textContent: text }, Object.assign({
      padding: "4px 8px", border: "1px solid #c4ccd6", borderRadius: "4px",
      background: "#f4f6f8", cursor: "pointer", fontSize: "12px",
    }, style || {}));
    b.addEventListener("click", onClick);
    return b;
  }
})();
