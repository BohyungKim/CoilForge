// ==UserScript==
// @name         CoilForge → CCSI Direct Coil autofill (review aid)
// @namespace    coilforge
// @version      2.0.0
// @description  Bridge the 13 Direct Coil drawing parameters from CoilForge straight into the external CCSI Online DX form — no copy/paste. Runs on both pages; CoilForge "Send to CCSI" pushes via the userscript manager's shared storage, the CCSI tab receives and opens a review-and-fill panel. Review aid only — you confirm every value; blocked/read-only fields are skipped; nothing auto-applies.
// @match        http://localhost:8011/*
// @match        http://127.0.0.1:8011/*
// @match        https://coil.ccsi.ie/*
// @grant        GM_setValue
// @grant        GM_getValue
// @grant        GM_addValueChangeListener
// @grant        GM_registerMenuCommand
// @run-at       document-idle
// ==/UserScript==

/*
 * ONE script, TWO roles (it detects which page it is on):
 *
 *   CoilForge (localhost:8011)  — adds a "▶ Send to CCSI" button. On click it reads
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
  const BRIDGE_KEY = "coilforge_ccsi_payload";
  const PANEL_ID = "coilforge-ccsi-autofill-panel";
  const STALE_MS = 10 * 60 * 1000;

  const onCoilForge =
    !!document.querySelector("#drawing-parameters") ||
    (location.hostname === "localhost" || location.hostname === "127.0.0.1");
  const onCcsi = location.hostname.endsWith("ccsi.ie");

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
    const fields = Object.keys(map.fields).map((key) => {
      const raw = dom[key];
      const has = raw !== undefined && raw !== "" && raw !== null;
      const num = Number(raw);
      const entry = map.fields[key] || {};
      return {
        key,
        ccsi_label: entry.ccsi_label || key,
        value: has ? (Number.isFinite(num) ? num : raw) : null,
        unit: entry.unit || "in",
        status: has ? "review_required" : "blocked",
        type: entry.type || "number",
        selectors: Array.isArray(entry.selectors) ? entry.selectors : [],
        blocked_reason: has ? null : "No value derived from the source or rule engine; review required.",
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
      el("strong", { textContent: "CoilForge → CCSI autofill" }),
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

    const fillAll = btn("Fill all reviewed", () => {
      payload.fields.forEach((f) => { if (isFillable(f)) fillOne(f); });
      summarize(payload);
    });
    fillAll.disabled = true;
    gateCheck.addEventListener("change", () => { fillAll.disabled = !gateCheck.checked; });

    body.append(gate, fillAll, el("div", { id: "ccsi-af-summary" }, { margin: "6px 0", fontSize: "12px" }));

    payload.fields.forEach((field) => {
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
        const b = btn("Fill", () => { fillOne(field); summarize(payload); });
        b.disabled = !resolved || resolved.readOnly;
        action.append(b);
      }
      row.append(label, mid, action);
      body.append(row);
    });
    summarize(payload);
  }

  function chip(field, resolved) {
    let text, color;
    if (!resolved && isFillable(field)) {
      text = "selector not found"; color = "#b3261e";
    } else if (resolved && resolved.readOnly && isFillable(field)) {
      text = `CCSI read-only (computed) — skipped, was ${resolved.value}`; color = "#6b7280";
    } else if (field.status === "blocked" || field.value === null || field.value === undefined) {
      text = `skipped — ${field.blocked_reason || "no value"}`; color = "#6b7280";
    } else if (field.status === "review_required") {
      text = `review: ${field.value}${field.unit ? " " + field.unit : ""}`; color = "#9a6700";
    } else {
      text = `${field.value}`; color = "#1a7f37";
    }
    return el("span", { textContent: text }, { color, fontSize: "12px", display: "inline-block", maxWidth: "230px" });
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
    if (target.readOnly) { markRow(field, "readonly"); return; }
    setNativeValue(target, field.value);
    ["input", "change", "blur"].forEach((type) => target.dispatchEvent(new Event(type, { bubbles: true })));
    markRow(field, verify(target, field) ? "ok" : "mismatch");
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

  function verify(target, field) {
    const got = String(target.value).trim();
    if (got === String(field.value).trim()) return true;
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
    const rows = payload.fields.map((f) => ({ f, t: resolve(f.selectors) }));
    const writable = rows.filter(({ f, t }) => isFillable(f) && t && !t.readOnly);
    const filled = writable.filter(({ f, t }) => verify(t, f) && String(t.value).trim() !== "").length;
    const readOnly = rows.filter(({ f, t }) => isFillable(f) && t && t.readOnly).length;
    const notFound = rows.filter(({ f, t }) => isFillable(f) && !t).length;
    const skipped = payload.fields.filter((f) => !isFillable(f)).length + readOnly;
    out.textContent =
      `${filled}/${writable.length} filled · ${skipped} skipped (blocked/no value/read-only)` +
      (notFound ? ` · ${notFound} selector(s) not found` : "");
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
