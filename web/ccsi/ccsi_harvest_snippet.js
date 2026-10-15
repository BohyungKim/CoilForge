// CoilForge — CCSI coil-form harvest snippet (READ-ONLY).
//
// Run via Claude-in-Chrome `javascript_tool` on an open coil editor
// (coil.ccsi.ie/Coils/Edit/{coilId}). It only READS the DOM: no value assignment,
// no event dispatch, no click, no submit (pinned by tests/test_ccsi_crosscheck.py).
// Every visible input/select is dumped — including ones the CoilForge map does not
// know yet, because those are exactly the "unmapped" fields the cross-check hunts.
//
// The record is parked on window.__cfHarvest and returned as JSON text; long
// records are read back in slices with window.__cfHarvestSlice(i).
(() => {
  const clean = (s) => (s || "").replace(/\s+/g, " ").trim();
  const sectionOf = (el) => {
    let node = el;
    while (node && node !== document.body) {
      let prev = node.previousElementSibling;
      while (prev) {
        const t = clean(prev.innerText);
        if (t && t === t.toUpperCase() && /[A-Z]/.test(t) && t.length < 40 && !prev.querySelector("input,select")) return t;
        prev = prev.previousElementSibling;
      }
      node = node.parentElement;
    }
    return null;
  };
  const labelOf = (el) => {
    if (el.id) {
      const l = document.querySelector(`label[for="${CSS.escape(el.id)}"]`);
      if (l) return clean(l.innerText);
    }
    let node = el;
    for (let depth = 0; depth < 3 && node; depth += 1) {
      let prev = node.previousElementSibling;
      while (prev) {
        const t = clean(prev.innerText);
        if (t && !prev.querySelector("input,select,textarea")) return t.slice(0, 60);
        prev = prev.previousElementSibling;
      }
      node = node.parentElement;
    }
    return null;
  };
  const visible = (el) => el.getBoundingClientRect().width > 0;
  const fields = {};
  document.querySelectorAll("input,select,textarea").forEach((el) => {
    if (!el.id || !visible(el) || ["button", "submit", "hidden"].includes(el.type)) return;
    const isSelect = el.tagName === "SELECT";
    const isToggle = el.type === "checkbox" || el.type === "radio";
    fields[el.id] = {
      label: labelOf(el),
      section: sectionOf(el),
      kind: isSelect ? "select" : el.type || "text",
      value: isSelect ? clean(el.selectedOptions[0] && el.selectedOptions[0].text) : isToggle ? el.checked : el.value,
      ro: Boolean(el.readOnly || el.disabled),
      options: isSelect ? Array.from(el.options).map((o) => clean(o.text)) : undefined,
    };
  });
  const hidden = (id) => {
    const el = document.getElementById(id);
    return el ? el.value : null;
  };
  const record = {
    schema: "coilforge.ccsi.harvest/1",
    url_path: location.pathname,
    component_type: hidden("ComponentType"),
    tag: fields.Tag ? fields.Tag.value : null,
    fields,
    harvested_at: new Date().toISOString(),
  };
  const text = JSON.stringify(record);
  window.__cfHarvest = text;
  window.__cfHarvestSlice = (i) => window.__cfHarvest.slice(i * 8000, (i + 1) * 8000);
  return { length: text.length, slices: Math.ceil(text.length / 8000), tag: record.tag, component_type: record.component_type, fields: Object.keys(fields).length };
})();
