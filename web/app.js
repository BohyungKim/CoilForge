const state = {
  ui: null,
  defaultInput: null,
  activeTab: "checklist",
  manualDrawingMode: false,
  compatibilityFilter: "all",
  pdfIntakeSummary: null,
  brainCase: null,
  selectedPdfFile: null,
  selectedQuotePdfFile: null,
  coverPageHint: "",
  pdfCoilPages: [],
  activePdfCoilPageIndex: -1,
  reviewedCoils: new Set(),
  productOptions: null,
  loadingProductOptions: false,
  lastTemplateDrawing: null,
};

const LEGACY_COMPATIBILITY_ENDPOINT = "/api/compatibility/default-review";
const MATCHED_REVIEW_ACTION = "use_matched_candidate_for_review";
const DIRECT_COIL_STANDARD_TUBE_DIAMETER = "3/8 1.00 x 0.866";
const DIRECT_COIL_TUBE_DIAMETER_OPTIONS = [
  "3/8 1.00 x 0.866",
  "1/2 1.25 x 1.0825",
  "5/8 1.50 x 1.299",
  "5/16 1.00 x 0.625",
  "3/8 1.00 x 0.75",
  "3/8 1.25 x 1.0825",
  "1/2 1.50 x 1.299",
];
const DIRECT_COIL_TUBE_MATERIAL_OPTIONS = [
  "Copper 0.012 Plain",
  "Copper 0.012 Rifled",
  "Copper 0.014 Plain",
  "Copper 0.016 Plain",
  "Copper 0.016 Rifled",
  "Copper 0.020 Plain",
  "Copper 0.020 Rifled",
];
const DIRECT_COIL_SYSTEM_TYPE_OPTIONS = [
  "Single-Circuit",
  "Dual-Circuit Intertwined",
  "Dual-Circuit Intertwined (uneven)",
  "Dual-Circuit Face-Split",
  "Dual-Circuit Face-Split (uneven)",
  "3-Circuit Intertwined",
  "3-Circuit Intertwined (uneven)",
  "3-Circuit Face-Split",
  "3-Circuit Face-Split (uneven)",
  "4-Circuit Intertwined",
  "2 Circ Int + 2 Circ Int",
];
const DIRECT_COIL_DX_DIST_CAPILLARY_SIZE = "1/4 x 0.025";
const DIRECT_COIL_DX_DIST_CAPILLARY_OPTIONS = [
  "3/16 x 0.025",
  "1/4 x 0.025",
  "5/16 x 0.025",
];
const REGISTERED_DRAWING_TEMPLATE_LABEL = "DX / Coil Hand Left / System Type Single-Circuit";
const DIRECT_COIL_FIXED_DRAWING_VALUES = {
  connections: "0-Standard",
  mountingholes: "None",
  distributorleadareamaxx: "0",
  distributorleadareamaxy: "0",
  cyclevalveleadlength: "0",
  applyventinganddrainingioconstraints: true,
  limitsrtostandardpositionsforeaseofmanufacture: false,
};

const elements = {
  breadcrumb: document.querySelector("#breadcrumb"),
  projectTree: document.querySelector("#project-tree"),
  savedStatus: document.querySelector("#saved-status"),
  draftId: document.querySelector("#draft-id"),
  groups: document.querySelector("#direct-coil-groups"),
  importSummary: document.querySelector("#import-summary"),
  sourceEvidence: document.querySelector("#source-evidence"),
  directCoilScreenMirror: document.querySelector("#direct-coil-screen-mirror"),
  pasteReadyCount: document.querySelector("#paste-ready-count"),
  pasteReadyFields: document.querySelector("#paste-ready-fields"),
  copyVisibleTsv: document.querySelector("#copy-visible-tsv"),
  drawingPreview: document.querySelector("#drawing-preview"),
  drawingParameters: document.querySelector("#drawing-parameters"),
  mechanicalFitSection: document.querySelector("#mechanical-fit-section"),
  mechanicalFitBody: document.querySelector("#mechanical-fit-body"),
  copyCcsiPayload: document.querySelector("#copy-ccsi-payload"),
  ccsiAutofillStatus: document.querySelector("#ccsi-autofill-status"),
  ccsiCompareBanner: document.querySelector("#ccsi-compare-banner"),
  ccsiBookmarklet: document.querySelector("#ccsi-bookmarklet"),
  ccsiBookmarkletStatus: document.querySelector("#ccsi-bookmarklet-status"),
  drawingTemplateStatus: document.querySelector("#drawing-template-status"),
  compatibilityStatus: document.querySelector("#compatibility-status"),
  compatibilitySummary: document.querySelector("#compatibility-summary"),
  compatibilityDecisions: document.querySelector("#compatibility-decisions"),
  decisionCaptureSummary: document.querySelector("#decision-capture-summary"),
  decisionCaptureItems: document.querySelector("#decision-capture-items"),
  performanceSummary: document.querySelector("#performance-summary"),
  validationSummary: document.querySelector("#validation-summary"),
  blockedFields: document.querySelector("#blocked-fields"),
  candidateStatus: document.querySelector("#candidate-status"),
  previewStatus: document.querySelector("#preview-status"),
  coilName: document.querySelector("#edit-coil-name"),
  finnedHeight: document.querySelector("#edit-finned-height"),
  finnedLength: document.querySelector("#edit-finned-length"),
  airflowDirection: document.querySelector("#edit-airflow-direction"),
  manualDrawingMode: document.querySelector("#manual-drawing-mode"),
  pdfIntakeFile: document.querySelector("#pdf-intake-file"),
  pdfIntakePanel: document.querySelector(".pdf-intake-panel"),
  pdfDropZone: document.querySelector("#pdf-drop-zone"),
  pdfFileName: document.querySelector("#pdf-file-name"),
  quotePdfFile: document.querySelector("#quote-pdf-file"),
  quotePdfDropZone: document.querySelector("#quote-pdf-drop-zone"),
  quotePdfFileName: document.querySelector("#quote-pdf-file-name"),
  pdfCoverPageInput: document.querySelector("#pdf-cover-page-input"),
  analyzePdf: document.querySelector("#analyze-pdf"),
  pdfIntakeSummary: document.querySelector("#pdf-intake-summary"),
  brainCaseBanner: document.querySelector("#brain-case-banner"),
  counts: {
    ready: document.querySelector("#count-ready"),
    review: document.querySelector("#count-review"),
    blocked: document.querySelector("#count-blocked"),
    unmapped: document.querySelector("#count-unmapped"),
  },
};

const DC_SECTIONS = {
  dxCoilData: [
    ["Tag", "input"],
    ["Coil Quantity", "input"],
    ["Tube Diameter (standard at top)", "select"],
    ["Tubes High", "input"],
    ["Finned Height(In)", "input"],
    ["Finned Length(In)", "input"],
    ["Rows Deep", "select"],
    ["Fins Per Inch", "select"],
    ["Number Of Feeds(Total)", "input"],
  ],
  dxCalculated: [
    ["Model Number", "model_number"],
    ["Rows Deep", "Rows Deep"],
    ["Number Of Feeds", "Number Of Feeds(Total)"],
    ["Fins Per Inch", "Fins Per Inch"],
    ["Supply Connection Qty", null],
    ["Supply Connection Size", null],
    ["Return Connection Qty", null],
    ["Return Connection Size", "Return Connection Size"],
    ["Face Area", null],
    ["External Surface Area", null],
    ["Coil Weight", null],
    ["Internal Volume", null],
  ],
  optionsLeft: [
    ["Tube Material", "select"],
    ["Fin Material", "select"],
    ["Fin Surface", "select"],
    ["Header Material", "select"],
    ["Header Wall Schedule", "select"],
    ["Connection Material", "select"],
    ["Connection Type", "select"],
    ["Return Connection Size", "select"],
    ["Casing Style", "select"],
  ],
  optionsRight: [
    ["Casing Material", "select"],
    ["Connection Ends", "select"],
    ["Coil Coating", "select"],
    ["Coil Hand", "select"],
    ["System Type", "select"],
    ["Drain Pan Type", "select"],
    ["Drain Pan Material", "select"],
    ["Drawing Notes", "input"],
  ],
  airLeft: [
    ["Total Air Flow(CFM)", "airflow"],
    ["Air Flow Per Coil(CFM)", "input"],
    ["Face Velocity(FPM)", "input"],
    ["Altitude(FT)", "input"],
    ["Entering Dry Bulb(°F)", "input"],
    ["Entering Wet Bulb(°F)", "input"],
    ["Entering Relative Humidity(%)", "input"],
    ["Leaving Dry Bulb(°F)", "input"],
    ["Total Capacity(MBH)(Per Coil)", "input"],
  ],
  airCalculated: [
    ["Standard Face Velocity", "Face Velocity(FPM)"],
    ["Entering Dry Bulb", "Entering Dry Bulb(°F)"],
    ["Entering Wet Bulb", "Entering Wet Bulb(°F)"],
    ["Leaving Dry Bulb", "Leaving Dry Bulb(°F)"],
    ["Leaving Wet Bulb", null],
    ["Air Pressure Drop", null],
    ["Total Capacity(All Coils)", "Total Capacity(MBH)(Per Coil)"],
    ["Sensible Capacity(All Coils)", null],
  ],
  refrigerantLeft: [
    ["Refrigerant", "select"],
    ["Evaporating Temperature(°F)", "input"],
    ["Liquid Temperature(°F)", "input"],
    ["Superheat(°F)", "input"],
    ["DXDistCapillarySize", "select"],
  ],
  refrigerantCalculated: [
    ["Refrigerant Velocity (connection)", "Refrigerant Velocity (connection)"],
    ["Refrigerant Pressure Drop", "Refrigerant Pressure Drop"],
    ["Refrigerant Mass Flow", "Refrigerant Mass Flow"],
  ],
};

// Header assembly 1 (the casing/fin column + the supply/return column). Header
// assemblies 2..N (I2/S2/O2/R2/HD2/ZD2, ...) are generated dynamically from the
// resolved parameter set by dcHeaderColumns(), so a 1HD coil shows no extra column
// while a 2HD/3HD/4HD coil grows one column per derived header.
const DC_DRAWING_COLUMNS = [
  [
    ["CD", true],
    ["BF", true],
    ["TF", true],
    ["RF", true],
    ["HF", true],
    ["CH", true],
    ["SL", false],
  ],
  [
    ["I", true],
    ["S", true],
    ["O", true],
    ["R", true],
    ["HD", false],
    ["ZD", false],
  ],
];

// Checkbox flag per logical dimension base, mirroring header-1's column above
// (positions I/S/O/R carry a checkbox; HD/ZD do not).
const DC_HEADER_ROW_FLAGS = [
  ["I", true],
  ["S", true],
  ["O", true],
  ["R", true],
  ["HD", false],
  ["ZD", false],
];

// Submittal Drawing-tab parameter layout: two Direct-Coil dimension columns
// (left = casing/fin, right = supply/return/header). Mirrors the Direct Coil
// software's panel so the same coil reads the same way in both. Any parameter
// resolved upstream but not listed here (e.g. HDx1) is appended to the right
// column so nothing is silently dropped.
const DRAWING_PARAM_COLUMNS = [
  ["CD", "BF", "TF", "RF", "HF", "CH", "SL"],
  ["I", "S", "O", "R", "HD", "ZD"],
];

const TAB_SECTION_TARGETS = {
  checklist: "#checklist-section",
  performance: "#performance-section",
  drawing: "#drawing-section",
  compatibility: "#compatibility-section",
  review: "#review-section",
};

async function requestJson(url, options = {}) {
  const response = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const payload = await response.json();
  if (!response.ok) {
    const message = payload?.detail || payload?.message || JSON.stringify(payload, null, 2);
    throw new Error(message);
  }
  return payload;
}

function statusClass(status) {
  return `status-${String(status || "unknown").replaceAll("_", "-")}`;
}

function formatValue(field) {
  if (field.value === null || field.value === undefined || field.value === "") {
    return "Not mapped";
  }
  return `${field.value}${field.unit ? ` ${field.unit}` : ""}`;
}

function renderShell(uiState) {
  state.ui = uiState;
  const project = uiState.project;
  const counts = uiState.readiness_report.summary_counts;
  const hasAnalyzedPdf = Boolean(uiState.pdf_intake_summary || state.pdfIntakeSummary);

  elements.breadcrumb.textContent = project.breadcrumb.join(" / ");
  elements.savedStatus.textContent = project.saved_status;
  elements.draftId.textContent = uiState.direct_coil_draft.draft_id;
  elements.counts.ready.textContent = counts.ready;
  elements.counts.review.textContent = counts.review_required;
  elements.counts.blocked.textContent = counts.blocked;
  elements.counts.unmapped.textContent = counts.unmapped;
  document.body.classList.toggle("is-init-stage", !hasAnalyzedPdf);

  renderDriverEditor(uiState);
  renderDirectCoilGroups(uiState);
  renderImportSummary(uiState);
  renderPasteReadyFields(uiState);
  renderDirectCoilScreenMirror(uiState);
  renderPdfIntakeSummary(uiState);
  renderDrawingParameters(uiState);
  renderDrawingPreview(uiState);
  renderCompatibilityReview(uiState);
  renderDecisionCapture(uiState);
  renderPerformance(uiState);
  renderValidation(uiState);
  renderBlockedFields(uiState);
  renderProjectTree(uiState);
  renderCoilReviewNav();
  updateQuoteGate();
  updateTabVisibility();
}

function renderProjectTree(uiState) {
  if (!elements.projectTree) {
    return;
  }
  elements.projectTree.innerHTML = "";
  const hasPdfPages = state.pdfCoilPages.length > 0;
  const projectButton = document.createElement("button");
  projectButton.className = `tree-item ${hasPdfPages ? "" : "active"}`;
  projectButton.type = "button";
  projectButton.textContent = hasPdfPages
    ? pdfProjectDisplayName(uiState) || "Imported PDF Coil Set"
    : uiState.project.project_name;
  projectButton.addEventListener("click", () => {
    if (!hasPdfPages) {
      return;
    }
    selectPdfCoilPage(state.activePdfCoilPageIndex >= 0 ? state.activePdfCoilPageIndex : 0);
  });
  elements.projectTree.append(projectButton);

  if (!hasPdfPages) {
    const draftButton = document.createElement("button");
    draftButton.className = "tree-item child muted";
    draftButton.type = "button";
    draftButton.textContent = "DX Header 1 Draft";
    elements.projectTree.append(draftButton);
    return;
  }

  state.pdfCoilPages.forEach((page, index) => {
    const pageButton = document.createElement("button");
    const reviewed = state.reviewedCoils.has(index);
    pageButton.className = `tree-item child ${index === state.activePdfCoilPageIndex ? "active" : ""}`;
    pageButton.type = "button";
    pageButton.dataset.coilPageIndex = String(index);
    pageButton.innerHTML = `
      <span>${reviewed ? "✓ " : ""}${escapeHtml(page.tag || `Coil ${index + 1}`)} x ${escapeHtml(page.quantity ?? "review")}</span>
      <em>${escapeHtml(page.coil_type || page.product_type || "current draft")}</em>
    `;
    pageButton.addEventListener("click", () => {
      selectPdfCoilPage(index);
    });
    elements.projectTree.append(pageButton);
  });
}

function selectPdfCoilPage(index) {
  const page = state.pdfCoilPages[index];
  if (!page?.workflow) {
    return;
  }
  state.activePdfCoilPageIndex = index;
  renderShell(workflowToUiState(state.ui, page.workflow, null));
  elements.savedStatus.textContent = `Showing ${page.tag || `coil ${index + 1}`} x ${page.quantity ?? "review"}`;
}

// Advance to a coil from the review-flow footer, then slide the drawing section in and
// scroll up to it so John starts the next coil at "Drawing Parameters & Drawing" rather
// than stranded at the bottom. Sidebar coil clicks keep using selectPdfCoilPage directly
// (no forced scroll) so casual browsing isn't jarring.
function advanceToCoil(index) {
  selectPdfCoilPage(index);
  const sec = document.querySelector("#drawing-section");
  if (!sec) {
    return;
  }
  // restart the slide-in animation (remove -> force reflow -> re-add)
  sec.classList.remove("coil-slide-in");
  void sec.offsetWidth;
  sec.classList.add("coil-slide-in");
  sec.scrollIntoView({ behavior: "smooth", block: "start" });
}

// Per-coil review footer: shows progress and lets John mark the active coil reviewed.
// Marking flips the button + bumps the counter, then advances to the next coil (slide +
// scroll to Drawing Parameters) so review flows straight through. On the last coil it just
// marks. The Next/Previous buttons move without marking. Quote package is gated until all
// coils are reviewed.
function markActiveCoilReviewed() {
  if (state.activePdfCoilPageIndex < 0) {
    return;
  }
  const idx = state.activePdfCoilPageIndex;
  state.reviewedCoils.add(idx);
  renderCoilReviewNav();       // flips button to "Reviewed ✓"
  renderProjectTree(state.ui); // adds the ✓ in the sidebar
  updateQuoteGate();           // bumps the gate/counter
  if (idx + 1 < state.pdfCoilPages.length) {
    advanceToCoil(idx + 1);    // slide + scroll to the next coil's Drawing Parameters
  }
}

function renderCoilReviewNav() {
  const nav = document.querySelector("#coil-review-nav");
  if (!nav) {
    return;
  }
  const total = state.pdfCoilPages.length;
  if (!total) {
    nav.innerHTML = "";
    return;
  }
  const idx = state.activePdfCoilPageIndex;
  const active = state.pdfCoilPages[idx] || {};
  const reviewed = state.reviewedCoils.has(idx);
  const hasPrev = idx > 0;
  const hasNext = idx + 1 < total;
  nav.innerHTML = `
    <div class="coil-review-progress">
      Coil ${idx + 1} of ${total} &middot; ${escapeHtml(active.tag || `Coil ${idx + 1}`)}
      &middot; ${state.reviewedCoils.size}/${total} reviewed
    </div>
    <button type="button" id="coil-mark-reviewed" class="secondary-action${reviewed ? " is-reviewed" : ""}">
      ${reviewed ? "Reviewed ✓" : "Mark reviewed ✓"}
    </button>
    <button type="button" id="coil-prev" class="secondary-action"${hasPrev ? "" : " disabled"}>&larr; Previous coil</button>
    <button type="button" id="coil-next" class="primary-button"${hasNext ? "" : " disabled"}>Next coil &rarr;</button>
  `;
  document.querySelector("#coil-mark-reviewed")?.addEventListener("click", markActiveCoilReviewed);
  document.querySelector("#coil-prev")?.addEventListener("click", () => {
    if (hasPrev) {
      advanceToCoil(idx - 1);
    }
  });
  document.querySelector("#coil-next")?.addEventListener("click", () => {
    if (hasNext) {
      advanceToCoil(idx + 1);
    }
  });
}

// "Build quote package" is the single end action: enabled only once every detected
// coil is reviewed. With no detected coils, it stays enabled (extraction fallback).
function updateQuoteGate() {
  const button = document.querySelector("#build-quote-package");
  if (!button) {
    return;
  }
  const total = state.pdfCoilPages.length;
  const allReviewed = !(total > 0 && state.reviewedCoils.size < total);
  const hasQuotePdf = isPdfFile(state.selectedQuotePdfFile);
  const blocked = !allReviewed || !hasQuotePdf;
  button.disabled = blocked;
  const hint = document.querySelector("#quote-package-section .quote-package-hint");
  let message = "";
  if (!allReviewed) {
    message = `Review all ${total} coil(s) above, then drop the quote PDF to build.`;
  } else if (!hasQuotePdf) {
    message = "All coils reviewed — drop the quote PDF below to build.";
  } else {
    message = "Ready to build the quote package.";
  }
  button.title = blocked ? message : "";
  if (hint) {
    hint.textContent = message;
  }
}

function renderPasteReadyFields(uiState) {
  const surface = uiState.direct_coil_paste_ready;
  if (!surface || !elements.pasteReadyFields) {
    return;
  }
  elements.pasteReadyCount.textContent = `${surface.total_fields} fields`;
  elements.pasteReadyFields.innerHTML = "";
  surface.fields.forEach((field) => {
    const row = document.createElement("tr");
    row.className = statusClass(field.status);
    row.dataset.pasteReadyRow = "true";
    row.dataset.copyEnabled = field.copy_enabled ? "true" : "false";
    row.dataset.label = field.direct_coil_label;
    row.dataset.value = field.value === null || field.value === undefined ? "" : String(field.value);
    row.dataset.status = field.status;
    row.dataset.section = field.section;

    appendTableCell(row, String(field.order));
    appendTableCell(row, field.section);
    appendTableCell(row, field.direct_coil_label);
    appendTableCell(row, field.display_value, "paste-value-cell");
    appendTableCell(row, field.status);
    appendTableCell(row, pasteReadyNotes(field), "paste-notes-cell");

    const copyCell = document.createElement("td");
    const copyValueButton = document.createElement("button");
    copyValueButton.type = "button";
    copyValueButton.className = "compact-copy";
    copyValueButton.textContent = "Value";
    copyValueButton.disabled = !field.copy_enabled;
    copyValueButton.addEventListener("click", () => {
      copyText(row.dataset.value);
    });
    const copyLabelButton = document.createElement("button");
    copyLabelButton.type = "button";
    copyLabelButton.className = "compact-copy secondary-action";
    copyLabelButton.textContent = "Label + value";
    copyLabelButton.disabled = !field.copy_enabled;
    copyLabelButton.addEventListener("click", () => {
      copyText(`${field.direct_coil_label}\t${row.dataset.value}`);
    });
    copyCell.append(copyValueButton, copyLabelButton);
    row.append(copyCell);
    elements.pasteReadyFields.append(row);
  });
}

function renderDirectCoilScreenMirror(uiState) {
  const surface = uiState.direct_coil_paste_ready;
  if (!surface || !elements.directCoilScreenMirror) {
    return;
  }
  const fieldsByLabel = buildDirectCoilFieldLookup(uiState, surface);
  const coilFormat = directCoilMirrorFormat(uiState);
  if (coilFormat === "condensing") {
    renderCondensingCoilScreenMirror(uiState, fieldsByLabel);
    return;
  }
  if (["chilled_water", "hot_water", "pre_hot_water", "post_hot_water"].includes(coilFormat)) {
    renderWaterCoilScreenMirror(coilFormat, fieldsByLabel);
    return;
  }
  elements.directCoilScreenMirror.innerHTML = `
    ${renderDcSection(
      "DX COIL DATA",
      renderDcTwoColumnForm(
        renderDcInputRows(DC_SECTIONS.dxCoilData, fieldsByLabel),
        renderDcCalculatedPanel(DC_SECTIONS.dxCalculated, fieldsByLabel, uiState),
      ),
    )}
    ${renderDcSection(
      "OPTIONS",
      renderDcTwoColumnForm(
        renderDcInputRows(DC_SECTIONS.optionsLeft, fieldsByLabel),
        renderDcInputRows(DC_SECTIONS.optionsRight, fieldsByLabel),
      ),
    )}
    ${renderDcSection(
      "AIR DATA",
      renderDcTwoColumnForm(
        renderDcInputRows(DC_SECTIONS.airLeft, fieldsByLabel),
        renderDcCalculatedPanel(DC_SECTIONS.airCalculated, fieldsByLabel, uiState),
      ),
    )}
    ${renderDcSection(
      "REFRIGERANT DATA",
      renderDcTwoColumnForm(
        renderDcInputRows(DC_SECTIONS.refrigerantLeft, fieldsByLabel),
        renderDcCalculatedPanel(DC_SECTIONS.refrigerantCalculated, fieldsByLabel, uiState),
      ),
    )}
    ${renderDcSection(
      "FOULING FACTORS",
      renderDcInputRows([["Air Side Fouling Factor(ft² °F h/Btu)", "input"]], fieldsByLabel),
    )}
    <div class="dc-ahri-note">
      Rated In Accordance With The Current Edition Of AHRI Std. 410. Coil is NOT certified by AHRI.
    </div>
    ${renderDcSection(
      "DRAWING PARAMETERS",
      renderDcDrawingParameters(uiState, fieldsByLabel),
    )}
  `;
  // The coil drawing is rendered on the dedicated Drawing tab
  // (renderDcEmbeddedDrawingPreview) rather than duplicated inside the mirror.
}

function buildDirectCoilFieldLookup(uiState, surface) {
  const fieldsByLabel = new Map();
  surface.fields.forEach((field) => {
    addDcFieldAlias(fieldsByLabel, field.direct_coil_label, field);
  });
  Object.values(uiState.direct_coil_draft?.fields || {}).forEach((field) => {
    addDcFieldAlias(fieldsByLabel, field.label, field);
    directCoilLabelsForDraftKey(field.field_key).forEach((label) => {
      addDcFieldAlias(fieldsByLabel, label, field);
    });
  });
  addCandidateFallbackFields(fieldsByLabel, activePdfCandidate());
  return fieldsByLabel;
}

function addDcFieldAlias(fieldsByLabel, label, field) {
  if (!label || !field) {
    return;
  }
  const existing = fieldsByLabel.get(label);
  if (!existing || (!hasMappedDcValue(existing) && hasMappedDcValue(field))) {
    fieldsByLabel.set(label, field);
  }
}

function setDcFieldAlias(fieldsByLabel, label, field) {
  if (!label || !field) {
    return;
  }
  fieldsByLabel.set(label, field);
}

function hasMappedDcValue(field) {
  return Boolean(
    field &&
      field.value !== null &&
      field.value !== undefined &&
      field.value !== "" &&
      field.status !== "unmapped" &&
      field.status !== "blocked",
  );
}

function directCoilLabelsForDraftKey(fieldKey) {
  const aliases = {
    tubes_high: ["Tubes High"],
    finned_height: ["Finned Height(In)"],
    finned_length: ["Finned Length(In)"],
    rows_deep: ["Rows Deep"],
    fins_per_inch: ["Fins Per Inch"],
    number_of_feeds: ["Number Of Feeds(Total)", "Number Of Feeds"],
    tube_material: ["Tube Material"],
    fin_material: ["Fin Material"],
    fin_surface: ["Fin Surface"],
    header_material: ["Header Material"],
    connection_material: ["Connection Material"],
    connection_type: ["Connection Type"],
    supply_connection_size: ["Supply Connection Size"],
    return_connection_size: ["Return Connection Size", "Connection Size"],
    casing_material: ["Casing Material"],
    casing_style: ["Casing Style"],
    connection_ends: ["Connection Ends"],
    coil_hand: ["Coil Hand"],
    system_type: ["System Type"],
    drain_pan_type: ["Drain Pan Type"],
    coil_coating: ["Coil Coating"],
    total_air_flow_cfm: ["Total Air Flow(CFM)", "Air Flow Per Coil(CFM)"],
    face_velocity_fpm: ["Face Velocity(FPM)", "Standard Face Velocity"],
    altitude_ft: ["Altitude(FT)"],
    entering_dry_bulb_f: ["Entering Dry Bulb(°F)", "Entering Dry Bulb"],
    entering_wet_bulb_f: ["Entering Wet Bulb(°F)", "Entering Wet Bulb"],
    relative_humidity_pct: ["Entering Relative Humidity(%)"],
    total_capacity_mbh: ["Total Capacity(MBH)(Per Coil)", "Total Capacity(All Coils)"],
    refrigerant: ["Refrigerant"],
    evaporating_temp_f: ["Evaporating Temperature(°F)", "Saturated Suction Temperature(°F)"],
    liquid_temp_f: ["Liquid Temperature(°F)"],
    superheat_f: ["Superheat(°F)"],
    dx_dist_capillary_size: ["DXDistCapillarySize"],
  };
  return aliases[fieldKey] || [];
}

function activePdfCandidate() {
  const page = state.pdfCoilPages[state.activePdfCoilPageIndex];
  return page?.workflow?.candidates?.[0] || null;
}

function addCandidateFallbackFields(fieldsByLabel, candidate) {
  if (!candidate) {
    return;
  }
  const dxCandidate = isDxPdfCandidate(candidate);
  setDcFieldAlias(
    fieldsByLabel,
    "Tube Diameter (standard at top)",
    directCoilCompanyRuleField(
      "tube_diameter_standard_at_top",
      DIRECT_COIL_STANDARD_TUBE_DIAMETER,
      "Direct Coil company rule: standard DX tube diameter is fixed for PDF review.",
    ),
  );
  if (candidate.tag) {
    addDcFieldAlias(fieldsByLabel, "Tag", candidateFallbackField(candidate.tag, "tag"));
  }
  if (candidate.quantity) {
    addDcFieldAlias(fieldsByLabel, "Coil Quantity", candidateFallbackField(candidate.quantity, "coil_quantity"));
  }
  if (dxCandidate) {
    addDxOptionsFallbackFields(fieldsByLabel, candidate);
    addDxAirFallbackFields(fieldsByLabel, candidate);
    addDxRefrigerantAndFoulingFallbackFields(fieldsByLabel);
  }
  const fallbackMap = [
    [candidate.geometry, "finned_height", ["Finned Height(In)", "Tubes High"]],
    [candidate.geometry, "finned_length", ["Finned Length(In)"]],
    [candidate.geometry, "rows_deep", ["Rows Deep"]],
    [candidate.geometry, "fins_per_inch", ["Fins Per Inch"]],
    [candidate.geometry, "number_of_feeds", ["Number Of Feeds(Total)", "Number Of Feeds"]],
    [candidate.geometry, "face_area_sqft", ["Face Area"]],
    [candidate.materials_construction, "tube_material", ["Tube Material"]],
    [candidate.materials_construction, "fin_material", ["Fin Material"]],
    [candidate.materials_construction, "fin_surface", ["Fin Surface"]],
    [candidate.materials_construction, "tube_surface", ["Tube Surface"]],
    [candidate.connections, "coil_hand", ["Coil Hand"]],
    [candidate.connections, "supply_connection_size", ["Supply Connection Size"]],
    [candidate.connections, "return_connection_size", ["Return Connection Size", "Connection Size"]],
    [candidate.connections, "qty_connections_per_header", ["Supply Connection Qty", "Return Connection Qty"]],
    [candidate.manufacturing_options, "coil_style", ["Coil Type", "Casing Style"]],
    [candidate.manufacturing_options, "coil_model", ["Model Number"]],
    [candidate.airside_conditions, "total_air_flow_cfm", ["Total Air Flow(CFM)", "Air Flow Per Coil(CFM)"]],
    [candidate.airside_conditions, "face_velocity_fpm", ["Face Velocity(FPM)", "Standard Face Velocity"]],
    [candidate.airside_conditions, "altitude_ft", ["Altitude(FT)"]],
    [candidate.airside_conditions, "entering_dry_bulb_f", ["Entering Dry Bulb(°F)", "Entering Dry Bulb"]],
    [candidate.airside_conditions, "entering_wet_bulb_f", ["Entering Wet Bulb(°F)", "Entering Wet Bulb"]],
    [candidate.airside_conditions, "fluid_type", ["Fluid Type"]],
    [candidate.airside_conditions, "fluid_percent", ["Fluid Ratio(%)"]],
    [candidate.airside_conditions, "fluid_entering_temp_f", ["Entering Fluid Temp(°F)"]],
    [candidate.airside_conditions, "fluid_leaving_temp_f", ["Leaving Fluid Temp(°F)"]],
    [candidate.airside_conditions, "fluid_flow_rate_gpm", ["Fluid Flow Rate(GPM)(All Coils)"]],
    [candidate.airside_conditions, "fluid_pressure_drop_ftwg", ["Fluid Pressure Drop(ftWG)"]],
    [candidate.performance, "total_capacity_mbh", ["Total Capacity(MBH)(Per Coil)", "Total Capacity(All Coils)"]],
    [candidate.performance, "air_pressure_drop_iwg", ["Air Pressure Drop"]],
    [candidate.performance, "internal_volume_cuin", ["Internal Volume"]],
    [candidate.performance, "refrigerant_pressure_drop_psi", ["Refrigerant Pressure Drop"]],
    [candidate.refrigerant_conditions, "refrigerant", ["Refrigerant"]],
    [candidate.refrigerant_conditions, "evaporating_temp_f", ["Evaporating Temperature(°F)", "Saturated Suction Temperature(°F)"]],
    [candidate.refrigerant_conditions, "liquid_temp_f", ["Liquid Temperature(°F)"]],
    [candidate.refrigerant_conditions, "superheat_f", ["Superheat(°F)"]],
    [candidate.refrigerant_conditions, "condensing_temp_f", ["Condensing Temperature(°F)"]],
    [candidate.refrigerant_conditions, "subcooling_f", ["Subcooling(°F)"]],
    [candidate.refrigerant_conditions, "vapor_temp_f", ["Vapor Temperature(°F)"]],
  ];
  fallbackMap.forEach(([group, key, labels]) => {
    const field = group?.[key];
    if (!field) {
      return;
    }
    labels.forEach((label) => {
      addDcFieldAlias(fieldsByLabel, label, candidateFallbackField(field, key));
    });
  });
}

function isDxPdfCandidate(candidate) {
  const typeText = [
    candidate.tag?.value,
    candidate.product_type?.value,
    candidate.coil_type?.value,
    candidate.header_type?.value,
  ]
    .filter(Boolean)
    .join(" ")
    .toUpperCase();
  return (
    typeText.includes("CDXC") ||
    typeText.includes("DX COIL") ||
    typeText.includes("DXC COOLING") ||
    typeText.includes("PRODUCT_TYPE: DX") ||
    typeText.split(/\s+/).includes("DX")
  ) && !typeText.includes("HGRC") && !typeText.includes("HGRH");
}

function addDxOptionsFallbackFields(fieldsByLabel, candidate) {
  const tubeMaterialField = directCoilTubeMaterialField(candidate);
  if (tubeMaterialField) {
    setDcFieldAlias(fieldsByLabel, "Tube Material", tubeMaterialField);
  }
  const optionRules = [
    ["Header Material", "Copper", "Direct Coil company rule for DX PDF review."],
    ["Header Wall Schedule", "(L)", "Direct Coil company rule for DX PDF review."],
    ["Connection Material", "Copper", "Direct Coil company rule for DX PDF review."],
    ["Connection Type", "Sweat", "Direct Coil company rule for DX PDF review."],
    ["Casing Style", "Standard", "Direct Coil company rule for DX PDF review."],
    ["Casing Material", "Galvanized Steel 16 gauge", "Direct Coil company rule for DX PDF review."],
    ["Connection Ends", "Same End Only", "Direct Coil company rule for DX PDF review."],
    ["Drain Pan Type", "None", "Direct Coil company rule for DX PDF review."],
    ["Drain Pan Material", "SST", "Direct Coil company rule for DX PDF review."],
  ];
  optionRules.forEach(([label, value, notes]) => {
    setDcFieldAlias(fieldsByLabel, label, directCoilCompanyRuleField(normalizeDcLabel(label), value, notes));
  });
  setDcFieldAlias(fieldsByLabel, "Coil Coating", directCoilCoatingField(candidate));
  const handField = candidate.connections?.coil_hand;
  if (handField) {
    setDcFieldAlias(
      fieldsByLabel,
      "Coil Hand",
      candidateFallbackField(
        {
          ...handField,
          notes: "Cover-page handing was mapped into Coil Hand; confirmation required before use.",
        },
        "coil_hand",
        "pdf_cover_page_handing_review",
      ),
    );
  }
  const systemTypeField = directCoilSystemTypeField(candidate);
  if (systemTypeField) {
    setDcFieldAlias(fieldsByLabel, "System Type", systemTypeField);
  }
}

function directCoilTubeMaterialField(candidate) {
  const sourceField = candidate.materials_construction?.tube_material;
  if (!sourceField) {
    return null;
  }
  const rawValue = String(sourceField.value || "").trim();
  const thicknessMatch = rawValue.match(/0\.\d{3}/);
  const thickness = thicknessMatch ? thicknessMatch[0] : null;
  const material = /copper/i.test(rawValue) || thickness ? "Copper" : rawValue;
  const value = material === "Copper" && thickness ? `Copper ${thickness} Plain` : rawValue;
  return {
    ...candidateFallbackField(sourceField, "tube_material", "pdf_tube_material_to_direct_coil_tube_material"),
    value,
    notes: "PDF Tube Material mapped to Direct Coil material option; Plain is the DX review default.",
  };
}

function directCoilCoatingField(candidate) {
  if (candidateHasCoatingReviewSignal(candidate)) {
    return directCoilReviewField(
      "coil_coating",
      "review required",
      "Coating-related PDF text detected; confirm coil coating before use.",
      "pdf_candidate_coating_review_signal",
    );
  }
  return directCoilCompanyRuleField(
    "coil_coating",
    "Plain",
    "Direct Coil default unless coating-related PDF text is detected.",
  );
}

function directCoilSystemTypeField(candidate) {
  const sourceField = candidate.connections?.qty_connections_per_header;
  const count = Number(sourceField?.value);
  const systemTypeByConnectionCount = {
    1: "Single-Circuit",
    2: "Dual-Circuit Intertwined",
    3: "3-Circuit Intertwined",
    4: "4-Circuit Intertwined",
  };
  const value = systemTypeByConnectionCount[count];
  if (!value) {
    return null;
  }
  return {
    ...candidateFallbackField(
      sourceField,
      "system_type",
      "pdf_qty_connections_per_header_to_direct_coil_system_type",
    ),
    value,
    notes: "System Type derived from PDF Qty Conn. / Header; review before use.",
  };
}

function addDxAirFallbackFields(fieldsByLabel, candidate) {
  const airflowField = candidate.airside_conditions?.total_air_flow_cfm;
  if (airflowField) {
    const mappedAirflow = candidateFallbackField(airflowField, "total_air_flow_cfm", "pdf_entering_airflow_to_direct_coil_airflow");
    setDcFieldAlias(fieldsByLabel, "Total Air Flow(CFM)", mappedAirflow);
    setDcFieldAlias(fieldsByLabel, "Air Flow Per Coil(CFM)", mappedAirflow);
  }
  const faceVelocityField = directCoilFaceVelocityField(candidate);
  if (faceVelocityField) {
    setDcFieldAlias(fieldsByLabel, "Face Velocity(FPM)", faceVelocityField);
    setDcFieldAlias(fieldsByLabel, "Standard Face Velocity", faceVelocityField);
  }
  const relativeHumidityField = directCoilRelativeHumidityField(candidate);
  if (relativeHumidityField) {
    setDcFieldAlias(fieldsByLabel, "Entering Relative Humidity(%)", relativeHumidityField);
  }
  setDcFieldAlias(
    fieldsByLabel,
    "Total Capacity(MBH)(Per Coil)",
    directCoilCompanyRuleField(
      "total_capacity_mbh_per_coil",
      0,
      "Direct Coil review default; software calculation will own final capacity.",
      "direct_coil_dx_capacity_review_default",
    ),
  );
}

function addDxRefrigerantAndFoulingFallbackFields(fieldsByLabel) {
  setDcFieldAlias(
    fieldsByLabel,
    "DXDistCapillarySize",
    directCoilCompanyRuleField(
      "dx_dist_capillary_size",
      DIRECT_COIL_DX_DIST_CAPILLARY_SIZE,
      "Direct Coil company rule: DX distributor capillary size is fixed for PDF review.",
      "direct_coil_dx_dist_capillary_company_rule",
    ),
  );
  setDcFieldAlias(
    fieldsByLabel,
    "Air Side Fouling Factor(ft² °F h/Btu)",
    directCoilCompanyRuleField(
      "air_side_fouling_factor",
      0,
      "Direct Coil company rule: air side fouling factor defaults to 0 for PDF review.",
      "direct_coil_air_side_fouling_company_rule",
    ),
  );
}

function directCoilFaceVelocityField(candidate) {
  const airflow = numberFromField(candidate.airside_conditions?.total_air_flow_cfm);
  const height = numberFromField(candidate.geometry?.finned_height);
  const length = numberFromField(candidate.geometry?.finned_length);
  if (!airflow || !height || !length) {
    return null;
  }
  const faceAreaSqft = (height * length) / 144;
  if (faceAreaSqft <= 0) {
    return null;
  }
  return directCoilComputedField(
    "face_velocity_fpm",
    roundTo(airflow / faceAreaSqft, 2),
    "fpm",
    "pdf_airflow_geometry_to_direct_coil_face_velocity",
    "Face Velocity calculated from Airflow CFM / ((Finned Height x Finned Length) / 144).",
  );
}

function directCoilRelativeHumidityField(candidate) {
  const dryBulbF = numberFromField(candidate.airside_conditions?.entering_dry_bulb_f);
  const wetBulbF = numberFromField(candidate.airside_conditions?.entering_wet_bulb_f);
  const altitudeFt = numberFromField(candidate.airside_conditions?.altitude_ft) || 0;
  const relativeHumidity = calculateRelativeHumidityPct(dryBulbF, wetBulbF, altitudeFt);
  if (relativeHumidity === null) {
    return null;
  }
  return directCoilComputedField(
    "relative_humidity_pct",
    roundTo(relativeHumidity, 2),
    "pct",
    "psychrometric_db_wb_to_relative_humidity",
    "Entering RH calculated from entering DB/WB and altitude using a review-aid psychrometric approximation.",
  );
}

function calculateRelativeHumidityPct(dryBulbF, wetBulbF, altitudeFt = 0) {
  if (!Number.isFinite(dryBulbF) || !Number.isFinite(wetBulbF) || wetBulbF > dryBulbF) {
    return null;
  }
  const dryBulbC = fahrenheitToCelsius(dryBulbF);
  const wetBulbC = fahrenheitToCelsius(wetBulbF);
  const pressureKpa = barometricPressureKpa(altitudeFt);
  const saturationWetBulb = saturationVaporPressureKpa(wetBulbC);
  const saturationDryBulb = saturationVaporPressureKpa(dryBulbC);
  if (saturationDryBulb <= 0) {
    return null;
  }
  const psychrometerCoefficient = 0.00066 * (1 + 0.00115 * wetBulbC);
  const vaporPressure = saturationWetBulb - psychrometerCoefficient * pressureKpa * (dryBulbC - wetBulbC);
  return clamp((vaporPressure / saturationDryBulb) * 100, 0, 100);
}

function saturationVaporPressureKpa(tempC) {
  return 0.61094 * Math.exp((17.625 * tempC) / (tempC + 243.04));
}

function barometricPressureKpa(altitudeFt) {
  const altitudeM = Math.max(0, Number(altitudeFt) || 0) * 0.3048;
  return 101.325 * Math.pow(1 - (2.25577e-5 * altitudeM), 5.2559);
}

function fahrenheitToCelsius(value) {
  return (value - 32) * (5 / 9);
}

function numberFromField(field) {
  const value = Number(field?.value);
  return Number.isFinite(value) ? value : null;
}

function roundTo(value, precision) {
  if (!Number.isFinite(value)) {
    return value;
  }
  const multiplier = 10 ** precision;
  return Math.round((value + Number.EPSILON) * multiplier) / multiplier;
}

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

function directCoilComputedField(key, value, unit, mappingRule, notes) {
  return {
    field_key: key,
    label: key,
    value,
    unit,
    status: "review_required",
    mapping_rule: mappingRule,
    source_ref: null,
    source_evidence_refs: [],
    notes,
  };
}

function candidateHasCoatingReviewSignal(candidate) {
  return textTreeContains(candidate, /\b(coat|coating|coated|epoxy|phenolic|heresite|e-coat|ecoat|fin guard)\b/i);
}

function textTreeContains(value, pattern, depth = 0) {
  if (depth > 6 || value === null || value === undefined) {
    return false;
  }
  if (typeof value === "string") {
    return pattern.test(value);
  }
  if (typeof value === "number" || typeof value === "boolean") {
    return false;
  }
  if (Array.isArray(value)) {
    return value.some((item) => textTreeContains(item, pattern, depth + 1));
  }
  return Object.values(value).some((item) => textTreeContains(item, pattern, depth + 1));
}

function candidateFallbackField(field, key, mappingRule = null) {
  return {
    ...field,
    field_key: key,
    status: field.status === "ready" ? "review_required" : (field.status || "review_required"),
    mapping_rule: mappingRule || field.mapping_rule || "pdf_candidate_review_fallback",
  };
}

function directCoilCompanyRuleField(key, value, notes, mappingRule = "direct_coil_company_rule") {
  return {
    field_key: key,
    label: key,
    value,
    unit: null,
    status: "review_required",
    mapping_rule: mappingRule,
    source_ref: null,
    source_evidence_refs: [],
    notes,
  };
}

function directCoilReviewField(key, value, notes, mappingRule) {
  return directCoilCompanyRuleField(key, value, notes, mappingRule);
}

function renderCondensingCoilScreenMirror(uiState, fieldsByLabel) {
  elements.directCoilScreenMirror.innerHTML = `
    ${renderDcSection(
      "CONDENSING COIL DATA",
      renderDcTwoColumnForm(
        renderDcInputRows([
          ["Tag", "input"],
          ["Coil Quantity", "input"],
          ["Tube Diameter (standard at top)", "select"],
          ["Coil Type", "select", null, "Standard"],
          ["Tubes High", "input"],
          ["Finned Height(In)", "input"],
          ["Finned Length(In)", "input"],
          ["Rows Deep", "select"],
          ["Fins Per Inch", "select"],
          ["Number Of Feeds", "input", "Number Of Feeds(Total)"],
        ], fieldsByLabel),
        `<div class="dc-command-stack">
          <button type="button">Calculate</button>
          <button class="secondary-action" type="button">Cancel</button>
        </div>`,
      ),
    )}
    ${renderDcSection(
      "OPTIONS",
      renderDcTwoColumnForm(
        renderDcInputRows([
          ["Tube Material", "select"],
          ["Fin Material", "select"],
          ["Fin Surface", "select"],
          ["Header Material", "select"],
          ["Header Wall Schedule", "select"],
          ["Connection Material", "select"],
          ["Connection Type", "select"],
          ["Supply Connection Size", "select"],
        ], fieldsByLabel),
        renderDcInputRows([
          ["Return Connection Size", "select"],
          ["Casing Material", "select"],
          ["Casing Style", "select"],
          ["Connection Ends", "select"],
          ["Coil Coating", "select"],
          ["Coil Hand", "select"],
          ["System Type", "select", null, "Single-Circuit"],
          ["Drawing Notes", "input"],
        ], fieldsByLabel),
      ),
    )}
    ${renderDcSection(
      "AIR DATA",
      renderDcInputRows([
        ["Total Air Flow(CFM)", "airflow"],
        ["Air Flow Per Coil(CFM)", "input"],
        ["Face Velocity(FPM)", "input"],
        ["Altitude(FT)", "input"],
        ["Entering Dry Bulb(°F)", "input"],
        ["Leaving Dry Bulb(°F)", "input"],
        ["Total Capacity(MBH)(Per Coil)", "input"],
      ], fieldsByLabel),
    )}
    ${renderDcSection(
      "REFRIGERANT DATA",
      renderDcInputRows([
        ["Refrigerant", "select"],
        ["Temperature Input", "select", null, "Vapor Temperature"],
        ["Saturated Suction Temperature(°F)", "input", "Evaporating Temperature(°F)"],
        ["Suction Temperature at Compressor(°F)", "input"],
        ["Vapor Temperature(°F)", "input"],
        ["Condensing Temperature(°F)", "input", "Liquid Temperature(°F)"],
        ["Subcooling(°F)", "input"],
        ["Separate Subcooling Tubes High", "input"],
        ["Separate Subcooling Circuits", "input"],
      ], fieldsByLabel),
    )}
    ${renderDcSection(
      "FOULING FACTORS",
      renderDcInputRows([["Air Side Fouling Factor(ft² °F h/Btu)", "input"]], fieldsByLabel),
    )}
  `;
}

function renderWaterCoilScreenMirror(coilFormat, fieldsByLabel) {
  const isHotWater = ["hot_water", "pre_hot_water", "post_hot_water"].includes(coilFormat);
  const title =
    coilFormat === "pre_hot_water"
      ? "PRE HOT WATER COIL DATA"
      : coilFormat === "post_hot_water"
        ? "POST HOT WATER COIL DATA"
        : isHotWater
          ? "HOT WATER COIL DATA"
          : "CHILLED WATER COIL DATA";
  elements.directCoilScreenMirror.innerHTML = `
    ${renderDcSection(
      title,
      renderDcTwoColumnForm(
        renderDcInputRows([
          ["Tag", "input"],
          ["Coil Quantity", "input"],
          ["Tube Diameter (standard at top)", "select"],
          ...(isHotWater ? [["Coil Type", "select", null, "Standard"]] : []),
          ["Tube Turbulators", "select", null, "No"],
          ["Tubes High", "input"],
          ["Finned Height(In)", "input"],
          ["Finned Length(In)", "input"],
          ["Rows Deep", "select"],
          ["Fins Per Inch", "select"],
          ["Number Of Feeds", "input", "Number Of Feeds(Total)"],
        ], fieldsByLabel),
        `<div class="dc-command-stack">
          <button type="button">Calculate</button>
          <button class="secondary-action" type="button">Cancel</button>
        </div>`,
      ),
    )}
    ${renderDcSection(
      "OPTIONS",
      renderDcTwoColumnForm(
        renderDcInputRows([
          ["Tube Material", "select"],
          ["Fin Material", "select"],
          ["Fin Surface", "select"],
          ["Header Material", "select"],
          ["Header Wall Schedule", "select"],
          ["Connection Material", "select"],
          ["Connection Type", "select"],
          ["Connection Size", "select", "Return Connection Size"],
          ["Casing Style", "select"],
          ...(isHotWater ? [] : [["Casing Material", "select"]]),
        ], fieldsByLabel),
        renderDcInputRows([
          ...(isHotWater ? [["Casing Material", "select"]] : []),
          ["Connection Ends", "select"],
          ["Coil Coating", "select"],
          ["Coil Hand", "select"],
          ["Air Flow Direction", "select", null, "Horizontal"],
          ["Drain and Vent", "select", null, "1/8\""],
          ["Drain and Vent Location", "select", null, "Stub/Connection"],
          ...(isHotWater ? [] : [["Drain Pan Type", "select"], ["Drain Pan Material", "select"]]),
          ["Drawing Notes", "input"],
        ], fieldsByLabel),
      ),
    )}
    ${renderDcSection(
      "AIR DATA",
      renderDcInputRows([
        ["Total Air Flow(CFM)", "airflow"],
        ["Air Flow Per Coil(CFM)", "input"],
        ["Face Velocity(FPM)", "input"],
        ["Altitude(FT)", "input"],
        ["Entering Dry Bulb(°F)", "input"],
        ...(isHotWater ? [] : [["Entering Wet Bulb(°F)", "input"], ["Entering Relative Humidity(%)", "input"]]),
        ["Leaving Dry Bulb(°F)", "input"],
        ["Total Capacity(MBH)(Per Coil)", "input"],
      ], fieldsByLabel),
    )}
    ${renderDcSection(
      "FLUID DATA",
      renderDcInputRows([
        ["Fluid Type", "select", null, isHotWater ? "Water" : "Propylene Glycol"],
        ["Fluid Ratio(%)", "input"],
        ["Entering Fluid Temp(°F)", "input"],
        ["Leaving Fluid Temp(°F)", "input"],
        ["Fluid Flow Rate(GPM)(All Coils)", "input"],
        ["Fluid Pressure Drop(ftWG)", "input"],
      ], fieldsByLabel),
    )}
    ${renderDcSection(
      "FOULING FACTORS",
      renderDcInputRows([
        ["Tube Side Fouling Factor(ft² °F h/Btu)", "input"],
        ["Air Side Fouling Factor(ft² °F h/Btu)", "input"],
      ], fieldsByLabel),
    )}
  `;
}

function directCoilMirrorFormat(uiState) {
  const activePage = state.pdfCoilPages[state.activePdfCoilPageIndex] || {};
  const tag = String(uiState.project?.coil_tag || activePage.tag || "").toUpperCase();
  const typeText = [
    activePage.coil_type,
    activePage.product_type,
    activePage.coil_format,
    uiState.import_summary?.selected_candidate?.coil_type,
  ]
    .filter(Boolean)
    .join(" ")
    .toUpperCase();
  if (
    tag.startsWith("CCWC-") ||
    typeText.includes("COOLING_CHILLED_WATER") ||
    typeText.includes("CHILLED") ||
    typeText.includes("CHW") ||
    typeText.includes("CCWC")
  ) {
    return "chilled_water";
  }
  if (
    tag.startsWith("PHWC-") ||
    typeText.includes("PREHEAT_HOT_WATER") ||
    typeText.includes("PRE_HOT_WATER") ||
    typeText.includes("PRE HOT WATER") ||
    typeText.includes("PREHEAT HWC") ||
    typeText.includes("HWC PRE-HEAT") ||
    typeText.includes("PHWC")
  ) {
    return "pre_hot_water";
  }
  if (
    tag.startsWith("HHWC-") ||
    typeText.includes("HEATING_HOT_WATER") ||
    typeText.includes("HEATING HWC") ||
    typeText.includes("HWC HEATING") ||
    typeText.includes("HHWC")
  ) {
    return "hot_water";
  }
  if (typeText.includes("HOT WATER") || typeText.includes("HW")) {
    return "hot_water";
  }
  if (
    tag.startsWith("RHHGRC-") ||
    tag.startsWith("HGRC-") ||
    typeText.includes("HGRH") ||
    typeText.includes("HGRC") ||
    typeText.includes("HOT GAS")
  ) {
    return "condensing";
  }
  return "dx";
}

function renderDcSection(title, body) {
  return `
    <section class="dc-screen-section">
      <h4 class="dc-green-title">${escapeHtml(title)}</h4>
      ${body}
    </section>
  `;
}

function renderDcTwoColumnForm(left, right) {
  return `
    <div class="dc-two-column">
      <div class="dc-form-column">${left}</div>
      <div class="dc-form-column">${right}</div>
    </div>
  `;
}

function renderDcInputRows(rows, fieldsByLabel) {
  return rows
    .map(([label, controlType, sourceLabel, fallbackValue]) =>
      renderDcInputRow(
        label,
        controlType,
        findDcField(fieldsByLabel, sourceLabel || label),
        fallbackValue,
      ),
    )
    .join("");
}

function renderDcInputRow(label, controlType, field, fallbackValue = null) {
  const fixedValue = fixedDcDrawingValue(label);
  const value =
    fixedValue !== null
      ? fixedValue
      : field
        ? dcControlValue(field)
        : (fallbackValue ?? "unmapped");
  const status =
    fixedValue !== null
      ? "review_required"
      : field?.status || (fallbackValue === null ? "unmapped" : "review_required");
  const className = `dc-control ${statusClass(status)}`;
  if (controlType === "airflow") {
    return `
      <label class="dc-form-row">
        <span>${escapeHtml(label)}</span>
        <div class="dc-inline-controls">
          <input class="${className}" value="${escapeHtml(value)}" readonly />
          <select class="dc-control dc-standard-select" disabled>
            <option>Standard</option>
            <option>unmapped</option>
          </select>
        </div>
      </label>
    `;
  }
  if (controlType === "select") {
    const options = dcSelectOptions(label, value);
    return `
      <label class="dc-form-row">
        <span>${escapeHtml(label)}</span>
        <select class="${className}" disabled>
          ${options.map((option) => `<option${option === value ? " selected" : ""}>${escapeHtml(option)}</option>`).join("")}
        </select>
      </label>
    `;
  }
  return `
    <label class="dc-form-row">
      <span>${escapeHtml(label)}</span>
      <input class="${className}" value="${escapeHtml(value)}" readonly />
    </label>
  `;
}

function dcSelectOptions(label, value) {
  if (normalizeDcLabel(label) === normalizeDcLabel("Tube Diameter (standard at top)")) {
    return DIRECT_COIL_TUBE_DIAMETER_OPTIONS;
  }
  if (normalizeDcLabel(label) === normalizeDcLabel("Tube Material")) {
    return withSelectedOption(DIRECT_COIL_TUBE_MATERIAL_OPTIONS, value);
  }
  if (normalizeDcLabel(label) === normalizeDcLabel("System Type")) {
    return withSelectedOption(DIRECT_COIL_SYSTEM_TYPE_OPTIONS, value);
  }
  if (normalizeDcLabel(label) === normalizeDcLabel("DXDistCapillarySize")) {
    return withSelectedOption(DIRECT_COIL_DX_DIST_CAPILLARY_OPTIONS, value);
  }
  return [value];
}

function withSelectedOption(options, value) {
  return options.includes(value) ? options : [value, ...options].filter(Boolean);
}

function findDcField(fieldsByLabel, label) {
  if (!label) {
    return null;
  }
  const exact = fieldsByLabel.get(label);
  if (exact) {
    return exact;
  }
  const normalizedLabel = normalizeDcLabel(label);
  for (const [fieldLabel, field] of fieldsByLabel.entries()) {
    if (normalizeDcLabel(fieldLabel) === normalizedLabel) {
      return field;
    }
  }
  return null;
}

function normalizeDcLabel(label) {
  return String(label || "")
    .replaceAll("Â", "")
    .replaceAll("²", "2")
    .replaceAll("°", "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "");
}

function renderDcCalculatedPanel(rows, fieldsByLabel, uiState) {
  return `
    <div class="dc-calculated-panel">
      ${rows
        .map(([label, source]) => {
          const value = dcCalculatedValue(source, fieldsByLabel, uiState);
          return `
            <div class="dc-calculated-row">
              <span>${escapeHtml(label)}</span>
              <strong>${escapeHtml(value)}</strong>
            </div>
          `;
        })
        .join("")}
    </div>
  `;
}

// Build one column per header assembly n>=2 present in the resolved parameter set.
// The resolver emits logical keys (I2/S2/O2/R2/HD2/ZD2, ...); we group by the
// trailing number so 2HD -> 1 extra column, 4HD -> 3 extra columns, 1HD -> none.
function dcHeaderColumns(uiState) {
  const params = uiState.drawing_parameters?.parameters || {};
  const headerNums = new Set();
  for (const key of Object.keys(params)) {
    const match = /^(?:I|S|O|R|HD|ZD)(\d+)$/.exec(key);
    if (match && Number(match[1]) >= 2) {
      headerNums.add(Number(match[1]));
    }
  }
  return [...headerNums]
    .sort((a, b) => a - b)
    .map((n) => DC_HEADER_ROW_FLAGS.map(([base, hasCheckbox]) => [`${base}${n}`, hasCheckbox]));
}

function renderDcDrawingParameters(uiState, fieldsByLabel) {
  const columns = [...DC_DRAWING_COLUMNS, ...dcHeaderColumns(uiState)];
  return `
    <div class="dc-drawing-grid">
      ${columns.map((column) => `
        <div class="dc-drawing-column">
          ${column.map(([label, hasCheckbox]) => renderDcDrawingRow(label, hasCheckbox, uiState, fieldsByLabel)).join("")}
        </div>
      `).join("")}
      <div class="dc-drawing-column dc-drawing-support">
        ${renderDcSelectRow("Connections", fieldsByLabel.get("Connections"))}
        ${renderDcSelectRow("Mounting Holes", fieldsByLabel.get("Mounting Holes"))}
      </div>
      <div class="dc-lead-fields">
        ${renderDcInputRow("Distributor Lead Area Max X", "input", fieldsByLabel.get("Distributor Lead Area Max X"))}
        ${renderDcInputRow("Distributor Lead Area Max Y", "input", fieldsByLabel.get("Distributor Lead Area Max Y"))}
        ${renderDcInputRow("Cycle Valve Lead Length", "input", fieldsByLabel.get("Cycle Valve Lead Length"))}
        ${renderDcCheckboxLine("Apply Venting and Draining I/O Constraints", fieldsByLabel.get("Apply Venting and Draining I/O Constraints"))}
        ${renderDcCheckboxLine("Limit S/R to Standard Positions (for ease of manufacture)", fieldsByLabel.get("Limit S/R to Standard Positions (for ease of manufacture)"))}
      </div>
    </div>
  `;
}

function renderDcDrawingRow(label, hasCheckbox, uiState, fieldsByLabel) {
  const parameter = uiState.drawing_parameters?.parameters?.[label];
  const pasteField = fieldsByLabel.get(label);
  const rawValue = parameter?.value ?? pasteField?.value;
  const value = rawValue === null || rawValue === undefined || rawValue === "" ? "unmapped" : String(rawValue);
  const status = parameter?.status || pasteField?.status || "unmapped";
  const checked = hasCheckbox && rawValue !== null && rawValue !== undefined && rawValue !== "";
  return `
    <label class="dc-dimension-row ${statusClass(status)}">
      <span>${escapeHtml(label)}</span>
      <input class="dc-dimension-check" type="checkbox" ${checked ? "checked" : ""} disabled />
      <input class="dc-control" data-ccsi-key="${escapeHtml(label)}" value="${escapeHtml(value)}" readonly />
    </label>
  `;
}

function renderDcSelectRow(label, field) {
  const fixedValue = fixedDcDrawingValue(label);
  const value = fixedValue !== null ? fixedValue : dcControlValue(field);
  const status = fixedValue !== null ? "review_required" : field?.status || "unmapped";
  return `
    <label class="dc-form-row dc-select-wide">
      <span>${escapeHtml(label)}</span>
      <select class="dc-control ${statusClass(status)}" disabled>
        <option>${escapeHtml(value)}</option>
      </select>
    </label>
  `;
}

function renderDcCheckboxLine(label, field) {
  const fixedValue = fixedDcDrawingValue(label);
  const checked = fixedValue !== null ? fixedValue === true : field?.value === true;
  const status = fixedValue !== null ? "review_required" : field?.status || "unmapped";
  return `
    <label class="dc-check-line ${statusClass(status)}">
      <input type="checkbox" ${checked ? "checked" : ""} disabled />
      <span>${escapeHtml(label)}</span>
    </label>
  `;
}

function fixedDcDrawingValue(label) {
  const key = normalizeDcLabel(label);
  if (Object.prototype.hasOwnProperty.call(DIRECT_COIL_FIXED_DRAWING_VALUES, key)) {
    return DIRECT_COIL_FIXED_DRAWING_VALUES[key];
  }
  return null;
}

function dcControlValue(field) {
  if (!field || field.status === "unmapped") {
    return "unmapped";
  }
  if (field.status === "blocked") {
    return "review required";
  }
  if (field.status === "calculated_read_only" && (field.value === null || field.value === undefined)) {
    return "calculated";
  }
  if (field.value === null || field.value === undefined || field.value === "") {
    return "unmapped";
  }
  return String(field.value);
}

function dcCalculatedValue(source, fieldsByLabel, uiState) {
  if (source === "model_number") {
    return uiState.drawing_intent?.model_number || "unmapped";
  }
  if (!source) {
    return "unmapped";
  }
  return dcControlValue(fieldsByLabel.get(source));
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function appendTableCell(row, value, className = "") {
  const cell = document.createElement("td");
  if (className) {
    cell.className = className;
  }
  cell.textContent = value;
  row.append(cell);
}

function pasteReadyNotes(field) {
  const evidence = field.source_evidence_refs?.length
    ? ` Evidence: ${field.source_evidence_refs.join(", ")}`
    : "";
  return `${field.notes}${evidence}`;
}

async function copyText(value) {
  const text = value === null || value === undefined ? "" : String(value);
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
    } else {
      fallbackCopyText(text);
    }
  } catch {
    fallbackCopyText(text);
  }
  elements.savedStatus.textContent = "Copied review-aid field value";
}

function fallbackCopyText(text) {
  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.setAttribute("readonly", "readonly");
  textarea.style.position = "fixed";
  textarea.style.left = "-9999px";
  document.body.append(textarea);
  textarea.select();
  document.execCommand("copy");
  textarea.remove();
}

// --- CCSI Online Direct Coil autofill -------------------------------------
// John hand-copies the 13 drawing parameters into the external CCSI Online
// "Direct Coil" DX form. This packages those 13 (and only those 13) into a
// clipboard JSON payload that the CCSI userscript (web/ccsi/ccsi_autofill.user.js)
// reads and fills. The selectors come from a same-origin field map so the
// userscript itself is generic; CCSI markup changes touch only the JSON.
const CCSI_AUTOFILL_SCHEMA = "coilforge.ccsi.autofill/1";
// Single source of truth for the scoped keys: the same 13 the panel lays out.
const CCSI_DRAWING_PARAM_KEYS = DRAWING_PARAM_COLUMNS.flat();

async function loadCcsiFieldMap() {
  if (state.ccsiFieldMap) {
    return state.ccsiFieldMap;
  }
  const response = await fetch("/static/ccsi/ccsi_dx_field_map.json", { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`field map fetch failed (${response.status})`);
  }
  state.ccsiFieldMap = await response.json();
  return state.ccsiFieldMap;
}

// Build the "drag once" bookmarklet from the SAME userscript source CoilForge
// serves, so there is one filler implementation. The userscript defines
// window.coilforgeCcsiAutofill but doesn't auto-open (it's menu-triggered under
// a manager); for the bookmarklet we append a call to open the panel.
async function setupCcsiBookmarklet() {
  const link = elements.ccsiBookmarklet;
  const status = elements.ccsiBookmarkletStatus;
  if (!link) {
    return;
  }
  try {
    const src = await fetch("/static/ccsi/ccsi_autofill.user.js", { cache: "no-store" })
      .then((response) => (response.ok ? response.text() : Promise.reject(response.status)));
    const code = `${src}\n;(window.coilforgeCcsiAutofill||function(){})();void 0`;
    link.href = `javascript:${encodeURIComponent(code)}`;
    if (status) {
      status.textContent = "Bookmarklet ready — drag “CCSI autofill” to your bookmarks bar.";
    }
  } catch (error) {
    link.removeAttribute("href");
    if (status) {
      status.textContent = `Could not build bookmarklet (${error}). Use the userscript option instead.`;
    }
  }
}

// The keys to push: the 13 base params, plus any multi-header keys (I2/S2/O2/R2/
// HD2/ZD2, I3/…) the coil actually produced AND the CCSI field map knows a selector
// for. Degrades to the 13 base for a 1HD coil, or when the map hasn't been extended
// with multi-header selectors yet — so it is always safe to call.
function ccsiFillKeys(parameters, fieldMap) {
  const keys = [...CCSI_DRAWING_PARAM_KEYS];
  const mapFields = fieldMap.fields || {};
  for (const key of Object.keys(parameters)) {
    const match = /^(?:I|S|O|R|HD|ZD)(\d+)$/.exec(key);
    if (match && Number(match[1]) >= 2 && mapFields[key] && !keys.includes(key)) {
      keys.push(key);
    }
  }
  return keys;
}

function buildCcsiAutofillPayload(uiState, fieldMap) {
  const parameters = uiState.drawing_parameters?.parameters || {};
  const fields = ccsiFillKeys(parameters, fieldMap).map((key) => {
    const parameter = parameters[key] || {};
    const mapEntry = fieldMap.fields?.[key] || {};
    const hasValue =
      parameter.value !== null && parameter.value !== undefined && parameter.value !== "";
    // Confidence gate carried one step further into the external form: a no-value
    // or unmapped parameter is "blocked" for fill purposes so the userscript skips
    // it. A real value rides along, but only ever as review_required — never an
    // auto-applied "ready" (the resolver emits no ready path for these 13).
    const status = hasValue ? parameter.status || "review_required" : "blocked";
    return {
      key,
      ccsi_label: mapEntry.ccsi_label || parameter.label || key,
      value: hasValue ? parameter.value : null,
      unit: parameter.unit || mapEntry.unit || "in",
      status,
      type: mapEntry.type || "number",
      selectors: Array.isArray(mapEntry.selectors) ? mapEntry.selectors : [],
      blocked_reason: hasValue
        ? null
        : parameter.blocked_reason || "No value derived from the source or rule engine; review required.",
    };
  });
  return {
    schema: CCSI_AUTOFILL_SCHEMA,
    generated_at: new Date().toISOString(),
    coil_tag: uiState.project?.coil_tag || null,
    review_aid_only: true,
    export_allowed: false,
    form: fieldMap.form || "CCSI Online Direct Coil — DX",
    field_map_version: fieldMap.version || "unknown",
    fields,
  };
}

// Phase 3 — CCSI safety compare. Given the CCSI form's CURRENT values (keyed by
// drawing-param, e.g. {R:"3.317", S:"6.188", I2:"3"}), compare each against the
// value CoilForge derived and colour the panel green (match) / red (mismatch). The
// compare runs server-side (/api/ccsi-compare) so the checklist comparator's 0.01"
// tolerance is the single source of truth. Review aid only — never writes to CCSI.
// Exposed on window so the Claude-in-Chrome filler (or the Tampermonkey bridge) can
// hand back the values it read from the form.
async function compareCcsi(ccsiValues) {
  const parameters = state.ui?.drawing_parameters?.parameters || {};
  const values = ccsiValues || {};
  const fields = Object.keys(values)
    .filter((key) => parameters[key])
    .map((key) => ({
      key,
      coilforge: parameters[key].value ?? null,
      ccsi: values[key] === "" ? null : values[key],
    }));
  if (!fields.length) {
    renderCcsiCompareBanner({ compared: 0, mismatch_count: 0 });
    return { compared: 0, mismatch_count: 0, fields: [] };
  }
  const response = await fetch("/api/ccsi-compare", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ fields }),
  });
  const report = await response.json();
  state.ccsiVerdicts = {};
  for (const row of report.fields || []) {
    state.ccsiVerdicts[row.key] = row;
  }
  renderDrawingParameters(state.ui);
  renderCcsiCompareBanner(report);
  return report;
}

function renderCcsiCompareBanner(report) {
  const el = elements.ccsiCompareBanner;
  if (!el) {
    return;
  }
  const mismatch = (report && report.mismatch_count) || 0;
  const compared = (report && report.compared) || 0;
  if (!compared) {
    el.hidden = true;
    el.textContent = "";
    el.classList.remove("has-mismatch");
    return;
  }
  el.hidden = false;
  el.classList.toggle("has-mismatch", mismatch > 0);
  el.textContent =
    mismatch > 0
      ? `⚠ ${mismatch} of ${compared} field(s) differ from CCSI — review before saving.`
      : `✓ all ${compared} compared field(s) match CCSI (within 0.01").`;
}

if (typeof window !== "undefined") {
  // The read-back path (Claude-in-Chrome or the TM bridge) calls this with the CCSI
  // form's current values to trigger the green/red compare.
  window.coilforgeCcsiCompare = compareCcsi;
  // Multi-coil sync (Tier 1 · /ccsi-sync-all): app.js is a module, so `state` and
  // selectPdfCoilPage aren't reachable from an injected script. Expose two thin,
  // read-only-ish entrypoints so the orchestration can list the project's coils and
  // switch the active one by index without reaching into module scope.
  window.coilforgeCoils = () =>
    (state.pdfCoilPages || []).map((page, index) => ({
      index,
      tag: page.tag || null,
      category: page.coil_category || null,
    }));
  window.coilforgeSelectCoil = (index) => {
    selectPdfCoilPage(index);
    return Boolean(state.ui?.drawing_parameters?.parameters);
  };
}

function renderPdfIntakeSummary(uiState) {
  if (!elements.pdfIntakeSummary) {
    return;
  }
  const summary = uiState.pdf_intake_summary || state.pdfIntakeSummary;
  if (!summary) {
    elements.pdfIntakeSummary.textContent = "No PDF analyzed.";
    return;
  }
  elements.pdfIntakeSummary.innerHTML = `
    ${ocrAlertBanner(summary)}
    <div class="pdf-summary-grid">
      <div><span>Source</span><strong>${escapeHtml(summary.source_filename || summary.source_id)}</strong></div>
      <div><span>Project Number</span><strong>${escapeHtml(summary.project_number || "review required")}</strong></div>
      <div><span>Project Name</span><strong>${escapeHtml(summary.project_name || "review required")}</strong></div>
      <div><span>Pages</span><strong>${escapeHtml(summary.pdf_pages)}</strong></div>
      <div><span>Engine</span><strong>${escapeHtml(summary.extraction_engine)}</strong></div>
      <div><span>Fields</span><strong>${escapeHtml(summary.extracted_field_count)}</strong></div>
      <div><span>Tag</span><strong>${escapeHtml(summary.selected_tag || "review required")}</strong></div>
      <div><span>Qty</span><strong>${escapeHtml(summary.selected_quantity ?? "review required")}</strong></div>
      <div><span>Handing</span><strong>${escapeHtml(summary.selected_handing || "review required")}</strong></div>
      <div><span>Coil pages</span><strong>${escapeHtml(coilPageCount(summary))}</strong></div>
      <div><span>Cover page</span><strong>${escapeHtml(coverPageStatus(summary))}</strong></div>
      <div><span>LLM OCR</span><strong>${escapeHtml(ocrStatus(summary))}</strong></div>
      <div><span>Text extraction</span><strong>${escapeHtml(extractionStatus(summary))}</strong></div>
      <div><span>Raw PDF stored</span><strong>${escapeHtml(summary.raw_pdf_stored ? "yes" : "no")}</strong></div>
    </div>
    ${renderPdfCoilReviewPages(summary)}
  `;
}

function ocrAlertBanner(summary) {
  if (!summary || !summary.ocr_blocked) {
    return "";
  }
  const message =
    summary.ocr_alert ||
    "OCR could not read this PDF's unreadable coil pages — values may be missing.";
  return `<div class="ocr-alert-banner">⚠ ${escapeHtml(message)}</div>`;
}

function extractionStatus(summary) {
  if (!summary.text_extraction_degraded) {
    return "ok";
  }
  const pages = summary.degraded_page_numbers?.length || 0;
  const ocrPages = summary.ocr_pages?.length || 0;
  if (ocrPages) {
    return `${pages} unreadable page(s), ${ocrPages} recovered via OCR (review required)`;
  }
  return `${pages} unreadable page(s) — set OPENAI_API_KEY or re-export submittal`;
}

function coilPageCount(summary) {
  return (summary.cover_page_rows?.length || state.pdfCoilPages.length || 1).toString();
}

function coverPageStatus(summary) {
  if (summary.cover_page_detected) {
    return `detected on page ${summary.cover_page_number} (${summary.cover_page_detection_method})`;
  }
  if (summary.cover_page_number) {
    return `manual page ${summary.cover_page_number}; OCR capture required`;
  }
  if (summary.cover_page_user_input_required) {
    return "not detected; enter cover page number";
  }
  return "not detected";
}

function ocrStatus(summary) {
  if (summary.ocr_status === "completed") {
    return `completed on page ${summary.ocr_page_number}`;
  }
  if (summary.ocr_status && summary.ocr_status !== "not_requested") {
    return summary.ocr_status;
  }
  if (summary.cover_page_ocr_required) {
    return "page input required";
  }
  return "not required";
}

function renderPdfCoilReviewPages(summary) {
  if (!state.pdfCoilPages.length) {
    let note = "No separate coil pages detected yet.";
    if (summary?.text_extraction_degraded) {
      note = summary.ocr_pages?.length
        ? "This PDF's coil pages use non-extractable fonts; text was recovered via OCR but no coil schedule matched — check the cover page number."
        : "This PDF's coil pages use non-extractable fonts, so the text could not be read. Set OPENAI_API_KEY to auto-OCR, enter the cover page number, or re-export the submittal.";
    }
    return `
      <section class="pdf-review-pages">
        <h4>Detected Coil Review Pages</h4>
        <p>${escapeHtml(note)}</p>
      </section>
    `;
  }
  return `
    <section class="pdf-review-pages" aria-label="Detected coil extraction review">
      <h4>Detected Coil Review Pages</h4>
      <div class="pdf-review-page-list">
        ${state.pdfCoilPages.map((page, index) => renderPdfCoilReviewPage(page, index)).join("")}
      </div>
    </section>
  `;
}

function renderPdfCoilReviewPage(page, index) {
  const workflow = page.workflow || {};
  const candidate = workflow.candidates?.[0] || {};
  const draft = workflow.direct_coil_input_draft || {};
  return `
    <details class="pdf-review-page">
      <summary>
        <span>${escapeHtml(page.tag || `Coil ${index + 1}`)}</span>
        <strong>${escapeHtml(page.coil_type || page.coil_format || "coil data")}</strong>
        <em>Qty ${escapeHtml(page.quantity ?? "review")}</em>
      </summary>
      <div class="pdf-review-page-body">
        <div class="pdf-review-meta">
          <div><span>Product</span><strong>${escapeHtml(page.product_type || "review")}</strong></div>
          <div><span>Format</span><strong>${escapeHtml(page.coil_format || "review")}</strong></div>
          <div><span>Handing</span><strong>${escapeHtml(page.handing || "review")}</strong></div>
          <div><span>Cover row</span><strong>${escapeHtml(page.cover_row_number ?? "review")}</strong></div>
        </div>
        <details class="pdf-review-section">
          <summary>Extracted Candidate Data</summary>
          ${renderCandidateFieldGroups(candidate)}
        </details>
        <details class="pdf-review-section">
          <summary>Mapped Direct Coil Draft Fields</summary>
          ${renderDraftFieldGroups(draft)}
        </details>
        <details class="pdf-review-section">
          <summary>Review Flags</summary>
          ${renderReviewFlags(workflow.selected_candidate_summary, workflow.canonical_summary)}
        </details>
      </div>
    </details>
  `;
}

function renderCandidateFieldGroups(candidate) {
  const groups = [
    ["Identity", { tag: candidate.tag, quantity: candidate.quantity, product_type: candidate.product_type, coil_type: candidate.coil_type, header_type: candidate.header_type }],
    ["Geometry", candidate.geometry],
    ["Airside Conditions", candidate.airside_conditions],
    ["Refrigerant Conditions", candidate.refrigerant_conditions],
    ["Materials & Construction", candidate.materials_construction],
    ["Connections", candidate.connections],
    ["Manufacturing Options", candidate.manufacturing_options],
    ["Performance", candidate.performance],
    ["Drawing Parameters", candidate.drawing_parameters],
  ];
  const rendered = groups
    .map(([label, fields]) => renderFieldValueGroup(label, fields))
    .filter(Boolean)
    .join("");
  return rendered || `<p>No extracted candidate fields available.</p>`;
}

function renderDraftFieldGroups(draft) {
  const fields = draft.fields || {};
  const groups = draft.groups || {};
  const rendered = Object.entries(groups)
    .map(([label, keys]) => {
      const groupFields = Object.fromEntries((keys || []).map((key) => [key, fields[key]]).filter(([, field]) => field));
      return renderFieldValueGroup(label, groupFields);
    })
    .filter(Boolean)
    .join("");
  return rendered || `<p>No mapped Direct Coil draft fields available.</p>`;
}

function renderFieldValueGroup(label, fields) {
  const rows = Object.entries(fields || {}).filter(([, field]) => field && field.value !== undefined && field.value !== null && field.value !== "");
  if (!rows.length) {
    return "";
  }
  return `
    <section class="pdf-field-group">
      <h5>${escapeHtml(label)}</h5>
      <table>
        <tbody>
          ${rows.map(([key, field]) => renderFieldValueRow(key, field)).join("")}
        </tbody>
      </table>
    </section>
  `;
}

function renderFieldValueRow(key, field) {
  const value = field?.value ?? "";
  const unit = field?.unit ? ` ${field.unit}` : "";
  const evidence = field?.source_evidence?.[0];
  const evidenceText = evidence
    ? `${evidence.source_key || key} / ${evidence.source_location || "source"}`
    : field?.mapping_rule || "";
  return `
    <tr>
      <th scope="row">${escapeHtml(formatFieldKey(key))}</th>
      <td>${escapeHtml(value)}${escapeHtml(unit)}</td>
      <td>${escapeHtml(field?.status || field?.confidence || "review_required")}</td>
      <td>${escapeHtml(evidenceText)}</td>
    </tr>
  `;
}

function renderReviewFlags(candidateSummary, canonicalSummary) {
  return `
    <div class="pdf-review-flags">
      <div><span>Candidate status</span><strong>${escapeHtml(candidateSummary?.review_status || "review")}</strong></div>
      <div><span>Candidate blocked</span><strong>${escapeHtml((candidateSummary?.blocked_fields || []).join(", ") || "none")}</strong></div>
      <div><span>Canonical status</span><strong>${escapeHtml(canonicalSummary?.validation_status || "review")}</strong></div>
      <div><span>Canonical blocked</span><strong>${escapeHtml((canonicalSummary?.blocked_fields || []).join(", ") || "none")}</strong></div>
    </div>
  `;
}

function formatFieldKey(key) {
  return String(key || "")
    .replace(/_/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function renderDriverEditor(uiState) {
  const fields = uiState.direct_coil_draft.fields;
  if (document.activeElement !== elements.coilName) {
    elements.coilName.value = uiState.drawing_intent.coil_name || "";
  }
  if (document.activeElement !== elements.finnedHeight) {
    elements.finnedHeight.value = fields.finned_height.value ?? "";
  }
  if (document.activeElement !== elements.finnedLength) {
    elements.finnedLength.value = fields.finned_length.value ?? "";
  }
  if (document.activeElement !== elements.airflowDirection) {
    elements.airflowDirection.value = fields.airflow_direction.value || "left_to_right";
  }
  elements.manualDrawingMode.checked = state.manualDrawingMode;
}

function renderDirectCoilGroups(uiState) {
  const { groups, fields } = uiState.direct_coil_draft;
  elements.groups.innerHTML = "";
  Object.entries(groups).forEach(([groupName, fieldKeys]) => {
    const section = document.createElement("section");
    section.className = "field-group";
    const title = document.createElement("h4");
    title.textContent = groupName;
    section.append(title);

    fieldKeys.forEach((key) => {
      const field = fields[key];
      const row = document.createElement("div");
      row.className = `draft-field ${statusClass(field.status)}`;
      row.dataset.group = groupName;
      row.dataset.fieldKey = field.field_key;
      row.innerHTML = `
        <div>
          <label>${field.label}</label>
          <span>${field.field_key}</span>
        </div>
        <output>${formatValue(field)}</output>
        <em>${field.status}</em>
      `;
      section.append(row);
    });
    elements.groups.append(section);
  });
}

function renderImportSummary(uiState) {
  const summary = uiState.import_summary;
  const candidate = summary.selected_candidate;
  elements.candidateStatus.textContent = candidate.review_status;
  elements.importSummary.innerHTML = `
    <div><span>Project</span><strong>${uiState.project.project_name}</strong></div>
    <div><span>Coil tag</span><strong>${uiState.project.coil_tag}</strong></div>
    <div><span>Candidate</span><strong>${candidate.candidate_id}</strong></div>
    <div><span>Review fields</span><strong>${candidate.review_required_fields.length}</strong></div>
    <div><span>Candidates</span><strong>${summary.candidate_count}</strong></div>
    <div><span>Raw data</span><strong>${summary.raw_private_data_included ? "present" : "excluded"}</strong></div>
  `;

  elements.sourceEvidence.innerHTML = "";
  const evidenceSummary = document.createElement("div");
  evidenceSummary.className = "evidence-summary";
  evidenceSummary.innerHTML = `
    <span>Evidence fields</span>
    <strong>${uiState.source_evidence.summary.fields_with_source_evidence}</strong>
  `;
  elements.sourceEvidence.append(evidenceSummary);

  uiState.source_evidence.fields.slice(0, 10).forEach((item) => {
    const row = document.createElement("div");
    row.className = "evidence-row";
    row.innerHTML = `<span>${item.label}</span><code>${item.evidence_ids.join(", ")}</code>`;
    elements.sourceEvidence.append(row);
  });
}

function renderDrawingPreview(uiState) {
  if (uiState.template_drawing && !uiState.template_drawing.error) {
    renderTemplateDrawingPreview(uiState.template_drawing);
    return;
  }
  const preview = uiState.drawing_preview;
  const templateState = currentDrawingTemplateState(uiState);
  if (elements.drawingTemplateStatus) {
    elements.drawingTemplateStatus.className = `drawing-template-status ${templateState.registered ? "status-review-required" : "status-blocked"}`;
    elements.drawingTemplateStatus.innerHTML = `
      <strong>${escapeHtml(templateState.label)}</strong>
      <span>${escapeHtml(templateState.reason)}</span>
    `;
  }
  if (!templateState.registered) {
    elements.previewStatus.textContent = "Not registered";
    elements.previewStatus.className = "status-chip status-blocked";
    elements.drawingPreview.innerHTML = renderTemplateNotRegisteredMessage(templateState);
    return;
  }
  elements.previewStatus.textContent = preview.preview_allowed ? "Preview ready" : "Blocked";
  elements.previewStatus.className = `status-chip ${preview.preview_allowed ? "status-review-required" : "status-blocked"}`;
  if (preview.svg) {
    elements.drawingPreview.innerHTML = preview.svg;
  } else {
    elements.drawingPreview.textContent = "Drawing preview blocked until required parameters are supplied.";
  }
}

// PDF reproduction path: the scanned CoilMaster drawing's as-built values were
// read directly and pushed into the matching seeded template. This is distinct
// from the header-engine prediction preview (drawing_preview.svg).
function renderTemplateDrawingPreview(templateDrawing) {
  state.lastTemplateDrawing = templateDrawing;
  const rendered = Boolean(templateDrawing.generation_allowed && templateDrawing.svg);
  if (elements.drawingTemplateStatus) {
    elements.drawingTemplateStatus.className = `drawing-template-status ${rendered ? "status-review-required" : "status-blocked"}`;
    elements.drawingTemplateStatus.innerHTML = `
      <strong>${escapeHtml(templateDrawingLabel(templateDrawing))}</strong>
      <span>${escapeHtml(templateDrawingReason(templateDrawing))}</span>
    `;
  }
  if (elements.previewStatus) {
    let chip;
    if (!rendered) {
      chip = "Not registered";
    } else {
      chip = templateDrawing.header_engine_used ? "Logic-derived" : "Linked — review dims";
    }
    elements.previewStatus.textContent = chip;
    elements.previewStatus.className = `status-chip ${rendered ? "status-review-required" : "status-blocked"}`;
  }
  elements.drawingPreview.innerHTML = `
    <div class="template-drawing-preview">
      <div class="template-drawing-caption">${templateDrawingCaption(templateDrawing)}</div>
      ${templateDrawingPicker(templateDrawing)}
      ${distributorOrientationBanner(templateDrawing)}
      <div class="template-drawing-canvas">${templateDrawingBody(templateDrawing, rendered)}</div>
    </div>
  `;
  attachCoilDrawingPicker(templateDrawing);
}

// NOTE: the per-coil "Drawing package (steps 9-12)" card (single-coil
// /api/package/assemble) was retired. The one end action is now "Build quote
// package" in the PDF-intake panel, which assembles every reviewed coil at once.

function arrayBufferToBase64(buffer) {
  const bytes = new Uint8Array(buffer);
  let binary = "";
  const chunk = 0x8000;
  for (let i = 0; i < bytes.length; i += chunk) {
    binary += String.fromCharCode.apply(null, bytes.subarray(i, i + chunk));
  }
  return btoa(binary);
}

// Name the exported quote package after the uploaded quote file with a "_Revised"
// suffix (e.g. "1234 Acme Quote.pdf" -> "1234 Acme Quote_Revised.pdf"). Falls back
// to the static name if no source file is in state.
function quotePackageExportName() {
  const sourceName = state.selectedQuotePdfFile?.name;
  if (!sourceName) return "coilforge-quote-package.pdf";
  const stem = sourceName.replace(/\.pdf$/i, "");
  return `${stem}_Revised.pdf`;
}

function downloadBase64Pdf(base64, fileName) {
  const bytes = Uint8Array.from(atob(base64), (c) => c.charCodeAt(0));
  const blob = new Blob([bytes], { type: "application/pdf" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = fileName;
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  URL.revokeObjectURL(url);
}

// Per-coil product line + unit size picker. A submittal does not state the
// CoilForge product line / unit size, which the rule engine needs to derive the
// header dimensions. When John picks them, /api/coil-drawing/derive re-runs the
// engine so CD/TF/BF/CH/HDx1/HD2/SL/I/O/R become logic-derived. Review-aid only.
async function ensureProductOptions() {
  if (state.productOptions || state.loadingProductOptions) {
    return;
  }
  state.loadingProductOptions = true;
  try {
    state.productOptions = await requestJson("/api/coil-drawing/product-options");
    if (state.lastTemplateDrawing) {
      renderTemplateDrawingPreview(state.lastTemplateDrawing);
    }
  } catch (error) {
    state.loadingProductOptions = false;
  }
}

function templateDrawingPicker(templateDrawing) {
  if (!templateDrawing.template_found) {
    return "";
  }
  const options = state.productOptions && state.productOptions.product_lines;
  if (!options) {
    ensureProductOptions();
    return `<div class="coil-drawing-picker"><span class="coil-picker-hint">Loading product lines…</span></div>`;
  }
  // Pre-fill the product line from the review-required suggestion derived from
  // the unit family (e.g. a Terra unit -> TERRA). The engineer still picks the
  // unit size to derive, so the engine gate is preserved.
  const curProduct = templateDrawing.product_type || templateDrawing.suggested_product_type || "";
  const curSize = templateDrawing.unit_size || "";
  const products = Object.keys(options);
  const sizes = options[curProduct] || [];
  const productOpts = [`<option value="">— product line —</option>`]
    .concat(products.map((p) =>
      `<option value="${escapeHtml(p)}"${p === curProduct ? " selected" : ""}>${escapeHtml(p)}</option>`))
    .join("");
  const sizeOpts = [`<option value="">— unit size —</option>`]
    .concat(sizes.map((s) =>
      `<option value="${escapeHtml(s)}"${s === curSize ? " selected" : ""}>${escapeHtml(s)}</option>`))
    .join("");
  const derived = templateDrawing.header_engine_used;
  const suggestion = !derived && templateDrawing.suggested_product_type
    ? ` Suggested from the unit type: ${templateDrawing.suggested_product_type}${
        templateDrawing.suggested_unit_size ? ` / ${templateDrawing.suggested_unit_size}` : ""
      } (review required).`
    : "";
  const derivedHint = templateDrawing.product_size_auto_detected
    ? "Auto-detected product line + unit size from the model code — review and override if needed:"
    : "Dimensions logic-derived for the selected product line + unit size:";
  return `
    <div class="coil-drawing-picker ${derived ? "is-derived" : "is-pending"}">
      <span class="coil-picker-hint">${derived
        ? escapeHtml(derivedHint)
        : "Pick a product line + unit size to derive the header dimensions (rule engine):" + escapeHtml(suggestion)}</span>
      <label>Product line
        <select id="coil-product-line">${productOpts}</select>
      </label>
      <label>Unit size
        <select id="coil-unit-size"${curProduct ? "" : " disabled"}>${sizeOpts}</select>
      </label>
    </div>
  `;
}

function attachCoilDrawingPicker(templateDrawing) {
  const productSel = document.querySelector("#coil-product-line");
  const sizeSel = document.querySelector("#coil-unit-size");
  if (!productSel || !sizeSel) {
    return;
  }
  const options = (state.productOptions && state.productOptions.product_lines) || {};
  productSel.addEventListener("change", () => {
    const sizes = options[productSel.value] || [];
    sizeSel.innerHTML = [`<option value="">— unit size —</option>`]
      .concat(sizes.map((s) => `<option value="${escapeHtml(s)}">${escapeHtml(s)}</option>`))
      .join("");
    sizeSel.disabled = !productSel.value;
  });
  sizeSel.addEventListener("change", () => {
    if (productSel.value && sizeSel.value) {
      deriveCoilDrawing(templateDrawing, productSel.value, sizeSel.value);
    }
  });
}

async function deriveCoilDrawing(templateDrawing, productLine, unitSize) {
  const ex = templateDrawing.extracted || {};
  const spec = {
    coil_category: ex.coil_category,
    coil_hand: ex.hand,
    circuits: ex.circuits,
    special_feature: ex.special_feature,
    tag: ex.tag,
    rows: ex.rows,
    feeds: ex.feeds,
    finned_height: ex.finned_height,
    finned_length: ex.finned_length,
    suction_conn_size: ex.return_conn_size,
    product_type: productLine,
    unit_size: unitSize,
    // Round-trip the submittal spec-panel values so the right-side panel stays
    // populated after the dimensions are logic-derived.
    panel: templateDrawing.panel,
  };
  if (elements.previewStatus) {
    elements.previewStatus.textContent = "Deriving…";
  }
  try {
    const updated = await requestJson("/api/coil-drawing/derive", {
      method: "POST",
      body: JSON.stringify(spec),
    });
    // The panel mirrors the drawing's slot values: refresh it from the re-derived
    // response so the Drawing Parameters stay aligned with the new dimensions.
    if (updated.drawing_parameter_set && state.ui) {
      state.ui.drawing_parameters = updated.drawing_parameter_set;
      renderDrawingParameters(state.ui);
    }
    renderTemplateDrawingPreview(updated);
    // The engineer just picked a product line + unit size, so the mechanical fit
    // can now evaluate. Update the active coil's fit inputs (preserving the rest
    // of the pair list) and re-run; fall back to just this coil if no PDF pages.
    const fitInput = fitInputFromSpec(spec);
    const active = state.pdfCoilPages[state.activePdfCoilPageIndex];
    if (active) {
      active.fit_inputs = fitInput;
      refreshMechanicalFit();
    } else {
      refreshMechanicalFit([fitInput]);
    }
  } catch (error) {
    if (elements.drawingTemplateStatus) {
      elements.drawingTemplateStatus.innerHTML = `
        <strong>Could not derive dimensions</strong>
        <span>${escapeHtml(error.message)}</span>
      `;
    }
  }
}

// Short coil classification summary (coil type / hand / header qty / HGBP) —
// the fields that actually pick a template, led with so the engineer sees what
// was classified rather than a bare dimension dump.
function coilClassificationSummary(templateDrawing) {
  const extracted = templateDrawing.extracted || {};
  const parts = [
    extracted.coil_category,
    extracted.hand,
    extracted.header_type
      || (extracted.circuits ? `Header ${extracted.circuits}` : null),
    extracted.special_feature ? `${extracted.special_feature} (special)` : null,
  ].filter(Boolean);
  return parts.join(" / ");
}

function templateDrawingLabel(templateDrawing) {
  const summary = coilClassificationSummary(templateDrawing);
  if (!templateDrawing.template_found) {
    return summary
      ? `${summary} — no matching drawing template registered`
      : "Could not classify this coil — REVIEW REQUIRED";
  }
  const prefix = summary ? `${summary} — ` : "";
  if (templateDrawing.generation_allowed && templateDrawing.svg) {
    return templateDrawing.header_engine_used
      ? `${prefix}logic-derived drawing (${templateDrawing.template_id})`
      : `${prefix}linked to ${templateDrawing.template_id} — dimensions REVIEW REQUIRED`;
  }
  if (templateDrawing.unregistered_product_line) {
    return `${prefix}template not registered (product line tracked separately — seed required)`;
  }
  return `${prefix}template not registered for this hand — seed required`;
}

function templateDrawingReason(templateDrawing) {
  if (templateDrawing.not_registered_reason) {
    return `${templateDrawing.not_registered_reason} Review-aid only.`;
  }
  if (!templateDrawing.template_found) {
    return "No catalog template matches this coil type / hand / header count. "
      + "Confirm the classification before relying on a drawing. Review-aid only.";
  }
  if (!templateDrawing.generation_allowed) {
    return "Template not registered for this coil hand — the mirror-derived pair is "
      + "disabled; each hand must be seeded from its own provided PDF. Review-aid only.";
  }
  if (!templateDrawing.header_engine_used) {
    return "Template linked from the submittal classification. Dimensions need a "
      + "product line + unit size to derive — unfilled values stay REVIEW REQUIRED. "
      + "Review-aid only — never manufacturing-approved.";
  }
  return "Dimensions logic-derived from the rule engine; values printed on any "
    + "as-built are read only to validate. Review-aid only — never manufacturing-approved.";
}

function templateDrawingCaption(templateDrawing) {
  const extracted = templateDrawing.extracted || {};
  const cells = [
    ["Tag", extracted.tag],
    ["Coil", extracted.coil_category],
    ["Hand", extracted.hand],
    ["Header", extracted.header_type],
    ["Special", extracted.special_feature],
    ["Circuits", extracted.circuits],
    ["Rows", extracted.rows],
    ["Feeds", extracted.feeds],
    ["Return conn.", extracted.return_conn_size],
    ["Unit size", templateDrawing.unit_size],
    ["Product", templateDrawing.product_type],
    ["Dims read", extracted.dimension_count],
  ].filter(([, value]) => value !== null && value !== undefined && value !== "");
  return cells
    .map(([label, value]) => `<span><em>${escapeHtml(label)}</em><strong>${escapeHtml(value)}</strong></span>`)
    .join("");
}

function templateDrawingBody(templateDrawing, rendered) {
  // Short term (2026-06-17): the registered EZ/CoilMaster template (params substituted,
  // server-side cleaned to numbers-only / no chrome) is the drawing surfaced for quotes &
  // revised-drawing requests — its geometry is verified. The parametric engine develops in
  // parallel and takes over once it reaches the template's accuracy. See [[drawing-direction]].
  if (rendered) {
    return templateDrawing.svg;
  }
  // Not rendered = no usable template is registered for this coil. Mirror-derived
  // hands are disabled (each hand must be seeded from its own PDF) and separately
  // tracked product lines (e.g. Ventum Plus) have no template yet — both surface
  // here as "template not registered" rather than borrowing another hand/line's art.
  const message = templateDrawing.not_registered_reason
    || "Template not registered for this coil — a seeded template (this hand / product line) "
       + "is required before a drawing can be generated. The classification below links it to the catalog.";
  const slots = templateDrawing.slot_values || {};
  const dims = Object.entries(slots)
    .filter(([key]) => key.startsWith("slot."))
    .map(([key, value]) => `<li><span>${escapeHtml(key.replace("slot.", ""))}</span><strong>${escapeHtml(value)}</strong></li>`)
    .join("");
  return `
    <div class="template-drawing-pending">
      <strong>${escapeHtml(templateDrawingLabel(templateDrawing))}</strong>
      <p>${escapeHtml(message)}</p>
      ${dims ? `<p class="template-drawing-slots-label">Values read so far (as-built):</p><ul class="template-drawing-slots">${dims}</ul>` : ""}
    </div>
  `;
}

// Loud review-required banner when the backend flagged that the drawn distributor
// orientation is not representative (Ventum+ DX draws ConnectionDown from the shared
// seeded template but R-032 requires ConnectionUp). Empty string when not flagged, so
// it renders nothing for every other coil. See submittal_to_drawing._flag_distributor_orientation_review.
function distributorOrientationBanner(templateDrawing) {
  const warning = templateDrawing && templateDrawing.distributor_orientation_warning;
  if (!warning) {
    return "";
  }
  return `<div class="drawing-orientation-warning">⚠ ${escapeHtml(warning)}</div>`;
}

function renderDrawingParameters(uiState) {
  const parameters = uiState.drawing_parameters?.parameters || {};
  const casing = DRAWING_PARAM_COLUMNS[0];
  const header1 = DRAWING_PARAM_COLUMNS[1];
  // Mirror the CCSI Direct Coil form: a casing column, then one column per header
  // assembly (Header 1 = I/S/O/R/HD/ZD, Header 2 = I2/S2/O2/R2/HD2/ZD2, ...). The
  // header index is the trailing digit of the logical key (same detection as
  // dcHeaderColumns). Degrades to casing | Header 1 for a 1HD coil (no n>=2 keys).
  const headerNums = new Set();
  for (const key of Object.keys(parameters)) {
    const match = /^(?:I|S|O|R|HD|ZD)(\d+)$/.exec(key);
    if (match && Number(match[1]) >= 2) {
      headerNums.add(Number(match[1]));
    }
  }
  const headerColumns = [...headerNums]
    .sort((a, b) => a - b)
    .map((n) => ["I", "S", "O", "R", "HD", "ZD"].map((base) => `${base}${n}`));
  // Any resolved parameter the fixed columns don't place (e.g. HDx1) rides along
  // under the casing column so nothing is silently dropped.
  const placed = new Set([...casing, ...header1, ...headerColumns.flat()]);
  const leftovers = Object.keys(parameters).filter((key) => !placed.has(key));
  const columns = [[...casing, ...leftovers], header1, ...headerColumns];
  elements.drawingParameters.innerHTML = columns
    .map(
      (column) => `
        <div class="dc-drawing-column">
          ${column
            .map((key) => parameters[key])
            .filter(Boolean)
            .map((parameter) => renderParameterRow(parameter))
            .join("")}
        </div>
      `,
    )
    .join("");
}

function renderParameterRow(parameter) {
  const hasValue =
    parameter.value !== null && parameter.value !== undefined && parameter.value !== "";
  // An empty drawing parameter is a warning, not a quiet gap: flag it RED and show
  // the English reason it couldn't be derived, inline + on hover (John 2026-06-27),
  // so a blank reads as "what's missing that we can fix together". Filled review
  // items keep the calm amber edge.
  const reason = hasValue
    ? ""
    : escapeHtml(
        parameter.blocked_reason ||
          "No value — not derived from the source or the rule engine.",
      );
  const emptyControl = hasValue ? "" : " dc-control--empty";

  // CCSI compare verdict (Phase 3): after "Compare vs CCSI", each field carries a
  // verdict. Match -> green edge; mismatch -> red edge + both values inline so a
  // divergence can't slip through before John saves the CCSI record. Review aid only.
  const cmp = state.ccsiVerdicts && state.ccsiVerdicts[parameter.key];
  let compareClass = "";
  let mismatchBadge = "";
  let compareTitle = "";
  if (cmp && cmp.verdict === "match") {
    compareClass = " dc-control--match";
  } else if (cmp && cmp.verdict === "mismatch") {
    compareClass = " dc-control--mismatch";
    const cf = cmp.coilforge === null || cmp.coilforge === undefined ? "—" : cmp.coilforge;
    const cc = cmp.ccsi === null || cmp.ccsi === undefined ? "—" : cmp.ccsi;
    compareTitle = escapeHtml(`CCSI ${cc} vs CoilForge ${cf} — review before saving`);
    mismatchBadge = `<span class="dc-dimension-mismatch">⚠ CCSI ${escapeHtml(String(cc))} &ne; CoilForge ${escapeHtml(String(cf))}</span>`;
  }
  // A mismatch tooltip wins over the empty-reason tooltip.
  const titleAttr = compareTitle || reason;
  // data-drawing-param / data-unit stay present in both modes so the derive
  // round-trip (collectDrawingPreviewValues) always finds the value; `readonly`
  // locks the field outside manual mode while keeping the Direct-Coil look.
  return `
    <label class="dc-dimension-row ${statusClass(parameter.status)}"${titleAttr ? ` title="${titleAttr}"` : ""}>
      <span>${escapeHtml(parameter.key)}</span>
      <input class="dc-dimension-check" type="checkbox" ${hasValue ? "checked" : ""} disabled />
      <input
        class="dc-control ${statusClass(parameter.status)}${emptyControl}${compareClass}"
        data-drawing-param="${escapeHtml(parameter.key)}"
        data-unit="${escapeHtml(parameter.unit || "in")}"
        type="number"
        step="0.01"
        value="${parameter.value ?? ""}"
        ${titleAttr ? `title="${titleAttr}"` : ""}
        ${state.manualDrawingMode ? "" : "readonly"}
      />
      ${mismatchBadge || (reason ? `<span class="dc-dimension-reason">⚠ ${reason}</span>` : "")}
    </label>
  `;
}

function currentDrawingTemplateState(uiState) {
  const surface = uiState.direct_coil_paste_ready;
  const fieldsByLabel = surface ? buildDirectCoilFieldLookup(uiState, surface) : new Map();
  return drawingTemplateState(uiState, fieldsByLabel);
}

function drawingTemplateState(uiState, fieldsByLabel) {
  const coilFormat = directCoilMirrorFormat(uiState);
  const hand = dcNormalizedValue(findDcField(fieldsByLabel, "Coil Hand"));
  const systemType = dcNormalizedValue(findDcField(fieldsByLabel, "System Type"));
  const isRegistered =
    coilFormat === "dx" &&
    ["left", "lh", "l"].includes(hand) &&
    systemType === "singlecircuit";
  if (isRegistered) {
    return {
      registered: true,
      label: REGISTERED_DRAWING_TEMPLATE_LABEL,
      reason: "Registered template: coilmaster_dx_lh_header1. Output remains review-aid only.",
    };
  }
  const displayFormat = coilFormat === "dx" ? "DX" : coilFormat.replaceAll("_", " ").toUpperCase();
  return {
    registered: false,
    label: "Template not registered",
    reason: `No drawing template is registered for ${displayFormat} / Coil Hand ${displayDcValue(findDcField(fieldsByLabel, "Coil Hand"))} / System Type ${displayDcValue(findDcField(fieldsByLabel, "System Type"))}.`,
  };
}

function renderDcEmbeddedDrawingPreview(uiState, fieldsByLabel) {
  const templateDrawing = uiState.template_drawing;
  if (templateDrawing && !templateDrawing.error) {
    const rendered = Boolean(templateDrawing.generation_allowed && templateDrawing.svg);
    return `
      <section class="dc-coil-drawing-panel">
        <div class="dc-coil-drawing-toolbar">
          <span>Coil Drawing</span>
          <strong>${rendered ? "Reproduced from PDF — review aid" : "Links — artwork not seeded"}</strong>
        </div>
        ${distributorOrientationBanner(templateDrawing)}
        <div class="dc-coil-drawing-canvas">
          ${templateDrawingBody(templateDrawing, rendered)}
        </div>
      </section>
    `;
  }
  const templateState = drawingTemplateState(uiState, fieldsByLabel);
  const preview = uiState.drawing_preview || {};
  const body =
    templateState.registered && preview.svg
      ? preview.svg
      : renderTemplateNotRegisteredMessage(templateState);
  return `
    <section class="dc-coil-drawing-panel">
      <div class="dc-coil-drawing-toolbar">
        <span>Coil Drawing</span>
        <strong>${templateState.registered ? "Review aid" : "Not registered"}</strong>
      </div>
      <div class="dc-coil-drawing-canvas">
        ${body}
      </div>
    </section>
  `;
}

function renderTemplateNotRegisteredMessage(templateState) {
  return `
    <div class="template-not-registered">
      <strong>${escapeHtml(templateState.label)}</strong>
      <span>${escapeHtml(templateState.reason)}</span>
    </div>
  `;
}

function dcNormalizedValue(field) {
  return String(dcControlValue(field))
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "");
}

function displayDcValue(field) {
  const value = dcControlValue(field);
  return value === "unmapped" ? "not mapped" : value;
}

function renderCompatibilityReview(uiState) {
  const review = uiState.compatibility_review;
  if (!review) {
    elements.compatibilityStatus.textContent = "Unavailable";
    elements.compatibilityDecisions.textContent = "Compatibility review data not loaded.";
    return;
  }
  const report = review.report;
  const registry = review.registry;
  const plan = review.reconciliation_plan;
  const safeSummary = review.safe_summary || {};
  elements.compatibilityStatus.textContent = plan.policy_status;
  elements.compatibilityStatus.className = "status-chip status-review-required";
  elements.compatibilitySummary.innerHTML = `
    <div><span>Case</span><strong>${report.case_id}</strong></div>
    <div><span>Exact matches</span><strong>${report.category_counts.exact_match}</strong></div>
    <div><span>Submittal only</span><strong>${report.category_counts.submittal_only}</strong></div>
    <div><span>EZ only</span><strong>${report.category_counts.ez_only}</strong></div>
    <div><span>Value mismatches</span><strong>${report.category_counts.value_mismatch}</strong></div>
    <div><span>Unit mismatches</span><strong>${report.category_counts.unit_mismatch}</strong></div>
    <div><span>Status mismatches</span><strong>${report.category_counts.status_mismatch}</strong></div>
    <div><span>Blocked mismatches</span><strong>${report.category_counts.blocked_mismatch}</strong></div>
    <div><span>Required issues</span><strong>${safeSummary.required_field_issues?.length ?? 0}</strong></div>
    <div><span>Drawing issues</span><strong>${safeSummary.drawing_impacting_issues?.length ?? 0}</strong></div>
    <div><span>Both-source rules</span><strong>${registry.summary.both_sources}</strong></div>
    <div><span>Export</span><strong>${plan.export_allowed ? "allowed" : "disabled"}</strong></div>
  `;
  elements.compatibilityDecisions.innerHTML = "";
  const decisionsByField = Object.fromEntries(plan.decisions.map((decision) => [decision.field_key, decision]));
  filteredCompatibilityComparisons(report.comparisons).slice(0, 30).forEach((comparison) => {
    const decision = decisionsByField[comparison.field_key] || {};
    const row = document.createElement("div");
    row.className = `compatibility-row ${compatibilityRowClass(decision, comparison)}`;
    row.dataset.action = decision.action || "";
    row.dataset.category = comparison.category;
    row.innerHTML = `
      <div>
        <strong>${comparison.field_key}</strong>
        <span>${comparison.canonical_path}</span>
      </div>
      <output>${compatibilityDisplayValue(comparison, decision)}</output>
      <em>${comparison.category} / ${decision.result_status || "review_required"}</em>
    `;
    elements.compatibilityDecisions.append(row);
  });
}

function filteredCompatibilityComparisons(comparisons) {
  if (state.compatibilityFilter === "matched") {
    return comparisons.filter((comparison) => comparison.status === "match");
  }
  if (state.compatibilityFilter === "exact_match") {
    return comparisons.filter((comparison) => comparison.category === "exact_match");
  }
  if (state.compatibilityFilter === "source_only") {
    return comparisons.filter((comparison) =>
      ["submittal_only", "ez_only"].includes(comparison.category),
    );
  }
  if (state.compatibilityFilter === "mismatch") {
    return comparisons.filter((comparison) =>
      ["value_mismatch", "unit_mismatch", "status_mismatch", "evidence_mismatch"].includes(
        comparison.category,
      ),
    );
  }
  if (state.compatibilityFilter === "blocked") {
    return comparisons.filter((comparison) => comparison.category === "blocked_mismatch");
  }
  if (state.compatibilityFilter === "held") {
    return comparisons.filter((comparison) => comparison.category !== "exact_match");
  }
  if (state.compatibilityFilter === "unmapped") {
    return comparisons.filter((comparison) => comparison.status === "missing_both");
  }
  return comparisons;
}

function compatibilityDisplayValue(comparison, decision) {
  if (comparison.category === "exact_match") {
    return `${comparison.submittal_value}${comparison.submittal_unit ? ` ${comparison.submittal_unit}` : ""}`;
  }
  if (decision.candidate_value !== null && decision.candidate_value !== undefined) {
    return decision.candidate_value;
  }
  return "Review required";
}

function compatibilityRowClass(decision, comparison) {
  if (comparison.category === "exact_match") {
    return "status-review-required";
  }
  if ((decision.action || "").includes("block_") || comparison.category.includes("mismatch")) {
    return "status-blocked";
  }
  return "status-unmapped";
}

function renderDecisionCapture(uiState) {
  const capture = uiState.decision_capture;
  if (!capture || !elements.decisionCaptureSummary || !elements.decisionCaptureItems) {
    return;
  }
  const summary = capture.summary || {};
  const baseline = capture.cd_bf_tf_ch_status || {};
  elements.decisionCaptureSummary.innerHTML = `
    <div><span>Packet</span><strong>${summary.decision_packet_status}</strong></div>
    <div><span>Drawing fields</span><strong>${summary.drawing_impacting ?? 0}</strong></div>
    <div><span>POs supported</span><strong>${summary.pos_supported ?? 0}</strong></div>
    <div><span>POs review</span><strong>${summary.pos_needs_john_review ?? 0}</strong></div>
    <div><span>CD/BF/TF/CH</span><strong>${Object.keys(baseline).join(", ")}</strong></div>
    <div><span>Export after decision</span><strong>${capture.export_allowed ? "allowed" : "disabled"}</strong></div>
  `;
  elements.decisionCaptureItems.innerHTML = "";
  (capture.items || []).slice(0, 12).forEach((item) => {
    const row = document.createElement("div");
    row.className = `decision-capture-row ${item.drawing_impact ? "status-review-required" : "status-unmapped"}`;
    row.innerHTML = `
      <div>
        <strong>${item.field_key}</strong>
        <span>${item.comparison_category} / ${item.current_approval_state}</span>
      </div>
      <select disabled aria-label="${item.field_key} proposed decision">
        <option>${item.proposed_decision}</option>
      </select>
      <em>${item.proposed_decision_status}</em>
    `;
    elements.decisionCaptureItems.append(row);
  });
}

function renderPerformance(uiState) {
  elements.performanceSummary.innerHTML = "";
  Object.values(uiState.performance_summary).forEach((item) => {
    const row = document.createElement("div");
    row.innerHTML = `<span>${item.label}</span><strong>${item.value ?? "Not mapped"} ${item.unit ?? ""}</strong>`;
    elements.performanceSummary.append(row);
  });
}

function renderValidation(uiState) {
  const validation = uiState.validation;
  elements.validationSummary.innerHTML = `
    <div><span>Workflow</span><strong>${validation.workflow_status}</strong></div>
    <div><span>Preview</span><strong>${validation.preview_allowed ? "allowed" : "blocked"}</strong></div>
    <div><span>Drawing</span><strong>${validation.drawing_status || "not_generated"}</strong></div>
    <div><span>Export</span><strong>${validation.export_status}</strong></div>
    <div><span>Blocked fields</span><strong>${validation.blocked_fields.length}</strong></div>
  `;
}

function renderBlockedFields(uiState) {
  elements.blockedFields.innerHTML = "";
  uiState.readiness_report.blocked_fields.forEach((field) => {
    const row = document.createElement("div");
    row.className = "blocked-row";
    row.innerHTML = `
      <strong>${field.field_key}</strong>
      <span>${field.label}</span>
      <em>${field.blocked_reason || "blocked"}</em>
    `;
    elements.blockedFields.append(row);
  });
}

const TAB_VIEWS = {
  checklist: "checklist",
  performance: "performance",
  drawing: "drawing",
  compatibility: "compatibility",
  review: "review",
};

function updateTabVisibility() {
  const activeView = TAB_VIEWS[state.activeTab] || "checklist";
  document.body.dataset.activeView = activeView;
  document.querySelectorAll("[data-tab]").forEach((button) => {
    button.classList.toggle("active", button.dataset.tab === state.activeTab);
  });
  // Real tabs: show only the blocks tagged for the active view.
  document.querySelectorAll("[data-view]").forEach((block) => {
    // data-view may list several views (space-separated) so one block can appear
    // under more than one tab (e.g. the drawing shows in both Checklist and Drawing).
    const views = (block.dataset.view || "").split(/\s+/).filter(Boolean);
    block.classList.toggle("is-hidden-view", !views.includes(activeView));
  });
  // Within the checklist view, every draft field row stays visible.
  document.querySelectorAll(".draft-field").forEach((row) => {
    row.hidden = false;
  });
}

function activateTab(tab, { scroll = false } = {}) {
  state.activeTab = tab;
  updateTabVisibility();
  if (!scroll) {
    return;
  }
  const target = document.querySelector(TAB_SECTION_TARGETS[tab]);
  if (target) {
    target.scrollIntoView({ behavior: "smooth", block: "start" });
  }
}

function workflowToUiState(previousUiState, workflow, workflowInput) {
  const readiness = workflow.readiness_report;
  const draft = workflow.direct_coil_input_draft;
  const coilName = workflow.drawing_intent.coil_name;
  const pdfProjectName = pdfProjectDisplayName({ pdf_intake_summary: workflow.pdf_intake_summary });
  return {
    ...previousUiState,
    project: {
      ...previousUiState.project,
      project_name: pdfProjectName || previousUiState.project.project_name,
      breadcrumb: workflow.pdf_intake_summary
        ? ["CoilForge", "PDF Intake", pdfProjectName || "Imported PDF Coil Set"]
        : previousUiState.project.breadcrumb,
      coil_tag: workflow.selected_candidate_summary.tag,
      saved_status: workflow.pdf_intake_summary
        ? "PDF candidate pre-populated for review"
        : "Workflow analyzed from sanitized demo",
    },
    import_summary: {
      ...previousUiState.import_summary,
      candidate_count: workflow.candidates?.length ?? previousUiState.import_summary.candidate_count,
      selected_candidate: workflow.selected_candidate_summary,
      raw_private_data_included: false,
      source_type: workflow.pdf_intake_summary ? "pdf_upload_candidate" : previousUiState.import_summary.source_type,
      pdf_parser_enabled: Boolean(workflow.pdf_intake_summary),
    },
    direct_coil_draft: {
      draft_id: draft.draft_id,
      source_canonical_record_id: draft.source_canonical_record_id,
      groups: draft.groups,
      fields: draft.fields,
      summary: draft.summary,
      coil_quantity: draft.coil_quantity,
      export_status: draft.export_status,
    },
    readiness_report: readiness,
    direct_coil_paste_ready: workflow.direct_coil_paste_ready,
    pdf_intake_summary: workflow.pdf_intake_summary || null,
    drawing_intent: workflow.drawing_intent,
    drawing_parameters: workflow.drawing_parameter_set,
    performance_summary: buildPerformanceSummary(draft),
    validation: {
      ...workflow.validation,
      readiness_counts: readiness.summary_counts,
      blocked_fields: readiness.blocked_fields.map((field) => field.field_key),
      review_required_fields: readiness.review_required_fields.map((field) => field.field_key),
      unmapped_field_count: readiness.unmapped_fields.length,
    },
    source_evidence: {
      summary: readiness.source_evidence_summary,
      fields: sourceEvidenceFields(readiness),
    },
    drawing_preview: {
      svg: workflow.svg,
      metadata: workflow.metadata,
      preview_allowed: workflow.validation.preview_allowed,
      export_allowed: workflow.validation.export_allowed,
    },
    template_drawing: workflow.template_drawing || null,
    actions: {
      ...previousUiState.actions,
      export_pdf: { enabled: false, placeholder: true },
    },
    workflow_payload_summary: {
      coil_name: coilName,
      finned_height: draft.fields.finned_height.value,
      finned_length: draft.fields.finned_length.value,
      airflow_direction: draft.fields.airflow_direction.value,
      preview_default_count: workflowInput?.preview_defaults?.length ?? 0,
    },
  };
}

function pdfProjectDisplayName(uiState) {
  const summary = uiState?.pdf_intake_summary || state.pdfIntakeSummary;
  const parts = [summary?.project_number, summary?.project_name].filter(Boolean);
  return parts.join(" / ");
}

function buildPerformanceSummary(draft) {
  const keys = [
    "total_air_flow_cfm",
    "entering_dry_bulb_f",
    "total_capacity_mbh",
    "refrigerant",
  ];
  return Object.fromEntries(
    keys
      .filter((key) => draft.fields[key])
      .map((key) => {
        const field = draft.fields[key];
        return [
          key,
          {
            label: field.label,
            value: field.value,
            unit: field.unit,
            status: field.status,
          },
        ];
      }),
  );
}

function sourceEvidenceFields(readiness) {
  return [...readiness.review_required_fields, ...readiness.blocked_fields]
    .filter((field) => field.source_evidence && field.source_evidence.length)
    .map((field) => ({
      field_key: field.field_key,
      label: field.label,
      status: field.status,
      evidence_ids: field.source_evidence.map((evidence) => evidence.evidence_id),
    }));
}

async function loadDefaultDemoWorkflow() {
  const [uiState, demo, compatibilityReview, decisionCapture] = await Promise.all([
    requestJson("/api/ui/default"),
    requestJson("/api/workflow/default-demo"),
    requestJson("/api/compatibility/default-demo"),
    requestJson("/api/compatibility/decision-capture"),
  ]);
  state.defaultInput = structuredClone(demo.input);
  state.manualDrawingMode = false;
  renderShell({
    ...uiState,
    compatibility_review: compatibilityReview,
    decision_capture: decisionCapture,
  });
}

async function runWorkflowFromCurrentState() {
  const workflowInput = buildWorkflowPayloadFromControls();
  const workflow = await requestJson("/api/workflow/submittal-to-drawing", {
    method: "POST",
    body: JSON.stringify(workflowInput),
  });
  state.defaultInput = workflowInput;
  renderShell(workflowToUiState(state.ui, workflow, workflowInput));
}

async function runWorkflowFromPdf() {
  const file = state.selectedPdfFile || elements.pdfIntakeFile.files?.[0];
  if (!file) {
    elements.pdfIntakeSummary.textContent = "Select a PDF before analyzing.";
    return;
  }
  setPdfAnalysisLoading(true);
  try {
    const pdfBytes = await file.arrayBuffer();
    const workflow = await requestJson("/api/workflow/pdf-to-drawing", {
      method: "POST",
      headers: {
        "Content-Type": "application/pdf",
        "X-CoilForge-Filename": sanitizeHeaderValue(file.name),
        "X-CoilForge-Source-Id": `PDF-UPLOAD-${Date.now()}`,
        ...coverPageHeader(),
      },
      body: pdfBytes,
    });
    state.brainCase = null;  // manual analyze replaces any case prefill context
    hydratePdfWorkflow(workflow, "PDF candidate pre-populated for review");
    renderBrainCaseBanner();
  } finally {
    setPdfAnalysisLoading(false);
  }
}

// Shared hydration for both intake paths (manual PDF upload and the PO Release
// board case deep link) — the case endpoint returns the same workflow shape.
function hydratePdfWorkflow(workflow, statusText) {
  state.pdfIntakeSummary = workflow.pdf_intake_summary;
  state.pdfCoilPages = workflow.pdf_coil_pages || [];
  state.activePdfCoilPageIndex = state.pdfCoilPages.length ? 0 : -1;
  state.reviewedCoils = new Set();  // fresh PDF -> nothing reviewed yet
  setSelectedQuotePdfFile(null);    // fresh analyze -> clear the prior quote PDF choice
  renderShell(workflowToUiState(state.ui, workflow, null));
  elements.savedStatus.textContent = statusText;
  refreshMechanicalFit();
  maybeAutoFillChecklist();  // background, best-effort — never blocks analyze
}

// --- PO Release board case prefill (?case=PRC-N deep link) ----------------- //
async function runWorkflowFromCase(caseId) {
  setPdfAnalysisLoading(true);
  const loadingLabel = elements.pdfIntakeSummary?.querySelector(".pdf-loading-indicator strong");
  if (loadingLabel) {
    loadingLabel.textContent = `Analyzing case ${caseId}'s submittal PDF...`;
  }
  elements.savedStatus.textContent = `Loading case ${caseId} from the PO Release board`;
  try {
    const workflow = await requestJson("/api/workflow/case-to-drawing", {
      method: "POST",
      body: JSON.stringify({ case_id: caseId }),
    });
    state.brainCase = workflow.brain_case || null;
    // Restore the File object BEFORE hydrating: checklist fill, quote package
    // and cover-page re-analyze all re-POST state.selectedPdfFile's bytes.
    await restoreCasePdfFile(caseId, state.brainCase?.source_filename);
    const label = state.brainCase?.label || caseId;
    hydratePdfWorkflow(workflow, `Case ${label} pre-analyzed from the PO Release board`);
    renderBrainCaseBanner();
  } catch (error) {
    state.brainCase = null;
    renderBrainCaseError(caseId, error);
  } finally {
    setPdfAnalysisLoading(false);
  }
}

async function restoreCasePdfFile(caseId, filename) {
  try {
    const response = await fetch(`/api/case/${encodeURIComponent(caseId)}/submittal-pdf`);
    if (!response.ok) {
      return;  // best-effort: downstream actions fall back to asking for a PDF
    }
    const blob = await response.blob();
    setSelectedPdfFile(new File([blob], filename || `${caseId}.pdf`, { type: "application/pdf" }));
  } catch {
    // best-effort only — the analysis itself already succeeded server-side
  }
}

function renderBrainCaseBanner() {
  const el = elements.brainCaseBanner;
  if (!el) {
    return;
  }
  const brainCase = state.brainCase;
  if (!brainCase) {
    el.setAttribute("hidden", "");
    el.classList.remove("has-mismatch");
    return;
  }
  const analyzedTags = new Set(
    (state.pdfCoilPages || []).map((page) => page.tag).filter(Boolean));
  const expected = brainCase.expected_coils || [];
  const rows = expected
    .map((coil) => {
      const found = analyzedTags.has(coil.tag);
      const qty = coil.qty ?? "?";
      const category = coil.category ? ` (${escapeHtml(coil.category)})` : "";
      const miss = found ? "" : " — not found in this analysis, review manually";
      return `<li class="${found ? "is-match" : "is-missing"}">` +
             `${escapeHtml(coil.tag)} × ${escapeHtml(qty)}${category}${miss}</li>`;
    })
    .join("");
  const expectation = expected.length
    ? `<span>Brain expects ${expected.length} coil(s) from the submittal scan:</span><ul>${rows}</ul>`
    : "<span>No coil requirement journaled for this case yet — review the analysis below.</span>";
  el.innerHTML =
    `<strong>PO Release board — ${escapeHtml(brainCase.label || brainCase.case_id)}</strong>${expectation}`;
  el.classList.toggle(
    "has-mismatch", expected.some((coil) => !analyzedTags.has(coil.tag)));
  el.removeAttribute("hidden");
}

function renderBrainCaseError(caseId, error) {
  const el = elements.brainCaseBanner;
  elements.savedStatus.textContent = "Case prefill failed — manual upload available";
  if (!el) {
    return;
  }
  el.innerHTML =
    `<strong>Case ${escapeHtml(caseId)} could not be pre-analyzed</strong>` +
    `<span>${escapeHtml(error?.message || String(error))}</span>` +
    `<span>Falling back to the demo view — drop the submittal PDF manually.</span>`;
  el.classList.add("has-mismatch");
  el.removeAttribute("hidden");
}

// --- Mechanical fit / Stability (review aid) ------------------------------ //
function collectFitInputs() {
  // Every analyzed coil carries compact fit_inputs from the workflow. Pairing
  // (DX+HGRH / CWC+HWC) is resolved server-side across the whole list.
  return state.pdfCoilPages.map((page) => page.fit_inputs).filter(Boolean);
}

// Map a coil-drawing derive spec to the /api/mechanical-fit coil-input shape.
function fitInputFromSpec(spec) {
  return {
    tag: spec.tag,
    coil_type: spec.coil_category,
    product_type: spec.product_type,
    unit_size: spec.unit_size,
    finned_height: spec.finned_height,
    finned_length: spec.finned_length,
    rows: spec.rows,
    feeds: spec.feeds,
    circuits: spec.circuits,
    suction_conn_size: spec.suction_conn_size,
  };
}

async function refreshMechanicalFit(overrideCoils) {
  const coils = overrideCoils || collectFitInputs();
  if (!coils.length) {
    elements.mechanicalFitSection?.setAttribute("hidden", "");
    return;
  }
  try {
    // installed_on_drain_pan: true so the pair check evaluates when a partner is
    // present (a quote pairing DX+HGRH / CWC+HWC almost always shares a drain pan).
    // No partner -> the report self-documents as "needs paired coil".
    const report = await requestJson("/api/mechanical-fit", {
      method: "POST",
      body: JSON.stringify({ coils, installed_on_drain_pan: true }),
    });
    renderMechanicalFit(report);
  } catch (err) {
    elements.mechanicalFitSection?.removeAttribute("hidden");
    elements.mechanicalFitBody.textContent = `Mechanical fit unavailable: ${err.message}`;
  }
}

function fitChip(verdict) {
  const v = verdict || "—";
  const cls =
    { PASS: "fit-pass", FAIL: "fit-fail", CANNOT_EVALUATE: "fit-review", NOT_APPLICABLE: "fit-na" }[
      v
    ] || "fit-review";
  return `<span class="fit-chip ${cls}">${escapeHtml(v)}</span>`;
}

function renderMechanicalFit(report) {
  elements.mechanicalFitSection?.removeAttribute("hidden");
  const coils = report.coils || [];
  if (!coils.length) {
    elements.mechanicalFitBody.textContent = "No coil with product line + unit size to evaluate.";
    return;
  }
  const cards = coils
    .map((c) => {
      const head = `<div class="fit-coil-head"><strong>${escapeHtml(c.tag || "coil")}</strong> <em>${escapeHtml(
        [c.coil_type, c.product_family, c.unit_size].filter(Boolean).join(" / ")
      )}</em></div>`;
      if (c.note) {
        return `<div class="fit-coil">${head}<p class="fit-note">⚠ ${escapeHtml(c.note)}</p></div>`;
      }
      const dp = c.drain_pan;
      const dpLine = dp
        ? `<div class="fit-line">${fitChip(dp.verdict)} <span>Drain pan</span> ${escapeHtml(dp.detail)}</div>`
        : "";
      return `
        <div class="fit-coil">
          ${head}
          <div class="fit-line">${fitChip(c.width && c.width.verdict)} <span>Width</span> ${escapeHtml(
            (c.width && c.width.detail) || "—"
          )}</div>
          <div class="fit-line">${fitChip(c.height && c.height.verdict)} <span>Height</span> ${escapeHtml(
            (c.height && c.height.detail) || "—"
          )}</div>
          ${dpLine}
        </div>`;
    })
    .join("");
  elements.mechanicalFitBody.innerHTML =
    cards +
    `<p class="fit-footer">Review aid — casing dims are review-required (R-074); a PASS is not an approval. export_allowed: ${
      report.export_allowed === true
    }.</p>`;
}

function setPdfAnalysisLoading(isLoading) {
  state.pdfAnalysisLoading = isLoading;
  elements.pdfIntakePanel?.classList.toggle("is-analyzing", isLoading);
  elements.pdfDropZone?.classList.toggle("is-analyzing", isLoading);
  elements.pdfIntakeSummary?.classList.toggle("is-analyzing", isLoading);
  elements.pdfIntakeSummary?.setAttribute("aria-busy", isLoading ? "true" : "false");
  elements.analyzePdf.disabled = isLoading;
  elements.analyzePdf.textContent = isLoading ? "Analyzing..." : "Analyze PDF";
  elements.pdfIntakeFile.disabled = isLoading;
  elements.pdfCoverPageInput.disabled = isLoading;
  if (!isLoading) {
    pdfProgress.stop();
    return;
  }
  elements.savedStatus.textContent = "Extracting PDF data for review";
  elements.pdfIntakeSummary.innerHTML = `
    <div class="pdf-loading-indicator" role="status" aria-live="polite" aria-busy="true">
      <div class="pdf-loading-head">
        <strong>Extracting PDF data...</strong>
        <span class="pdf-loading-pct" data-role="pct">0%</span>
      </div>
      <div class="pdf-progress" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0">
        <div class="pdf-progress-fill" data-role="fill" style="width:2%"></div>
      </div>
      <span class="pdf-loading-step" data-role="step">Reading the submittal...</span>
    </div>
  `;
  pdfProgress.start();
}

// Determinate progress for the PDF analyze POST. The endpoint is one blocking call
// whose internal stages aren't observable from the browser, so we ease a "trickle"
// bar toward a sub-100 cap and rotate the step label by %-band — honest motion that
// never claims completion. The real finish is the results grid replacing the loading
// card (renderPdfIntakeSummary overwrites #pdf-intake-summary), so there is no forced
// 100% frame. stop() clears the interval on every teardown path.
const pdfProgress = (() => {
  let timer = null;
  let current = 0;

  function stepLabel(pct) {
    if (pct < 15) return "Extracting PDF text";
    if (pct < 35) return "Parsing cover rows";
    if (pct < 55) return "Detecting coil sections";
    if (pct < 75) return "Classifying product line";
    return "Building drawing";
  }

  function paint() {
    const summary = elements.pdfIntakeSummary;
    const fill = summary?.querySelector('[data-role="fill"]');
    if (!fill) {  // card was replaced by results (or torn down) — nothing to drive
      stop();
      return;
    }
    const rounded = Math.round(current);
    fill.style.width = `${rounded}%`;
    const pct = summary.querySelector('[data-role="pct"]');
    if (pct) pct.textContent = `${rounded}%`;
    const bar = summary.querySelector('[role="progressbar"]');
    if (bar) bar.setAttribute("aria-valuenow", String(rounded));
    const step = summary.querySelector('[data-role="step"]');
    if (step) step.textContent = stepLabel(current);
  }

  function stop() {
    if (timer !== null) {
      clearInterval(timer);
      timer = null;
    }
  }

  function start() {
    stop();  // defensive: never run two intervals (e.g. case deep-link + button)
    current = 2;
    paint();
    timer = setInterval(() => {
      current += (92 - current) * 0.09;  // eased trickle, decelerates toward the cap
      paint();
    }, 350);
  }

  return { start, stop };
})();

function sanitizeHeaderValue(value) {
  return String(value || "").replace(/[\r\n]/g, " ").slice(0, 180);
}

function coverPageHeader() {
  const value = elements.pdfCoverPageInput.value.trim();
  if (!value) {
    return {};
  }
  return { "X-CoilForge-Cover-Page": sanitizeHeaderValue(value) };
}

function setSelectedPdfFile(file) {
  if (!file) {
    state.selectedPdfFile = null;
    elements.pdfFileName.textContent = "No file selected";
    elements.pdfDropZone.classList.remove("has-file");
    return;
  }
  state.selectedPdfFile = file;
  elements.pdfFileName.textContent = file.name;
  elements.pdfDropZone.classList.add("has-file");
  elements.pdfIntakeSummary.textContent = "PDF ready for local analysis.";
}

// Dedicated quote-PDF input at the bottom of the review scroll (separate from the top
// submittal drop). Re-checks the build gate so picking the PDF enables the button.
function setSelectedQuotePdfFile(file) {
  if (!isPdfFile(file)) {
    state.selectedQuotePdfFile = null;
    if (elements.quotePdfFileName) elements.quotePdfFileName.textContent = "No file selected";
    elements.quotePdfDropZone?.classList.remove("has-file");
  } else {
    state.selectedQuotePdfFile = file;
    if (elements.quotePdfFileName) elements.quotePdfFileName.textContent = file.name;
    elements.quotePdfDropZone?.classList.add("has-file");
  }
  updateQuoteGate();
}

function isPdfFile(file) {
  return file && (file.type === "application/pdf" || file.name.toLowerCase().endsWith(".pdf"));
}

function setPdfDragActive(active) {
  elements.pdfDropZone.classList.toggle("is-drag-active", active);
}

function buildWorkflowPayloadFromControls() {
  const base = structuredClone(state.defaultInput);
  base.title_block = {
    ...(base.title_block || {}),
    coil_name: elements.coilName.value.trim() || "SANITIZED WORKFLOW PREVIEW",
  };
  base.submittal_text = replaceSanitizedLine(
    base.submittal_text,
    "FINNED_HEIGHT",
    `${numberOrFallback(elements.finnedHeight.value, 0)} in`,
  );
  base.submittal_text = replaceSanitizedLine(
    base.submittal_text,
    "FINNED_LENGTH",
    `${numberOrFallback(elements.finnedLength.value, 0)} in`,
  );
  base.submittal_text = replaceSanitizedLine(
    base.submittal_text,
    "AIRFLOW_DIRECTION",
    elements.airflowDirection.value,
  );
  base.preview_defaults = state.manualDrawingMode
    ? collectDrawingPreviewValues()
    : structuredClone(base.preview_defaults || []);
  return base;
}

function replaceSanitizedLine(text, key, value) {
  const pattern = new RegExp(`^${key}:.*$`, "m");
  const replacement = `${key}: ${value}`;
  if (pattern.test(text)) {
    return text.replace(pattern, replacement);
  }
  return `${text.trimEnd()}\n${replacement}\n`;
}

function collectDrawingPreviewValues() {
  return [...document.querySelectorAll("[data-drawing-param]")]
    .map((input) => ({
      key: input.dataset.drawingParam,
      value: numberOrFallback(input.value, null),
      unit: input.dataset.unit || "in",
      source: "sanitized_fixture/default",
      reason: "UI review-required preview value",
    }))
    .filter((item) => item.value !== null);
}

function numberOrFallback(rawValue, fallback) {
  const parsed = Number(rawValue);
  return Number.isFinite(parsed) ? parsed : fallback;
}

document.querySelectorAll("[data-tab]").forEach((button) => {
  button.addEventListener("click", () => {
    activateTab(button.dataset.tab, { scroll: true });
  });
});

document.querySelectorAll("[data-compat-filter]").forEach((button) => {
  button.addEventListener("click", () => {
    state.compatibilityFilter = button.dataset.compatFilter;
    document.querySelectorAll("[data-compat-filter]").forEach((filterButton) => {
      filterButton.classList.toggle("active", filterButton === button);
    });
    renderCompatibilityReview(state.ui);
  });
});

elements.manualDrawingMode.addEventListener("change", () => {
  state.manualDrawingMode = elements.manualDrawingMode.checked;
  renderDrawingParameters(state.ui);
});

elements.copyVisibleTsv.addEventListener("click", () => {
  const rows = [...document.querySelectorAll("[data-paste-ready-row='true']")];
  const header = [
    "#",
    "Direct Coil Section",
    "Direct Coil Field",
    "Value to Copy",
    "Status",
    "Copy Enabled",
  ].join("\t");
  const body = rows.map((row) =>
    [
      row.children[0].textContent,
      row.dataset.section,
      row.dataset.label,
      row.dataset.value || row.children[3].textContent,
      row.dataset.status,
      row.dataset.copyEnabled,
    ].join("\t"),
  );
  copyText([header, ...body].join("\n")).catch((error) => {
    elements.savedStatus.textContent = error.message;
  });
});

elements.copyCcsiPayload?.addEventListener("click", async () => {
  if (!state.ui?.drawing_parameters) {
    elements.ccsiAutofillStatus.textContent = "Run an analysis first — no drawing parameters yet.";
    return;
  }
  try {
    const fieldMap = await loadCcsiFieldMap();
    const payload = buildCcsiAutofillPayload(state.ui, fieldMap);
    await copyText(JSON.stringify(payload, null, 2));
    const fillable = payload.fields.filter((field) => field.value !== null).length;
    elements.ccsiAutofillStatus.textContent =
      `Copied CCSI payload — ${fillable}/${payload.fields.length} fields have a value to review (map v${payload.field_map_version}). Switch to the CCSI form and run the userscript.`;
  } catch (error) {
    elements.ccsiAutofillStatus.textContent = `Could not build payload: ${error.message}`;
  }
});

setupCcsiBookmarklet();

document.querySelector("#analyze")?.addEventListener("click", () => {
  runWorkflowFromCurrentState().catch((error) => {
    elements.validationSummary.textContent = error.message;
  });
});

elements.analyzePdf.addEventListener("click", () => {
  runWorkflowFromPdf().catch((error) => {
    const message = formatPdfAnalysisError(error);
    elements.pdfIntakeSummary.textContent = message;
    elements.savedStatus.textContent = message;
  });
});

function formatPdfAnalysisError(error) {
  const rawMessage = error?.message || String(error || "Unknown PDF analysis error.");
  if (rawMessage.includes("Unable to extract text from PDF bytes")) {
    return [
      "PDF analysis failed: text could not be extracted from this PDF.",
      "If this is a scanned/image PDF, enter the cover page number and enable OCR credentials before retrying.",
      rawMessage,
    ].join(" ");
  }
  if (rawMessage.includes("X-CoilForge-Cover-Page")) {
    return `PDF analysis failed: ${rawMessage}`;
  }
  return `PDF analysis failed: ${rawMessage}`;
}

elements.pdfIntakeFile.addEventListener("change", () => {
  setSelectedPdfFile(elements.pdfIntakeFile.files?.[0] || null);
});

elements.pdfCoverPageInput.addEventListener("change", () => {
  state.coverPageHint = elements.pdfCoverPageInput.value.trim();
});

["dragenter", "dragover"].forEach((eventName) => {
  elements.pdfDropZone.addEventListener(eventName, (event) => {
    event.preventDefault();
    setPdfDragActive(true);
  });
});

["dragleave", "drop"].forEach((eventName) => {
  elements.pdfDropZone.addEventListener(eventName, (event) => {
    event.preventDefault();
    setPdfDragActive(false);
  });
});

elements.pdfDropZone.addEventListener("drop", (event) => {
  const file = event.dataTransfer?.files?.[0] || null;
  if (!isPdfFile(file)) {
    elements.pdfIntakeSummary.textContent = "Only PDF files can be analyzed.";
    return;
  }
  setSelectedPdfFile(file);
});

// Dedicated bottom quote-PDF drop + file input.
elements.quotePdfFile?.addEventListener("change", () => {
  setSelectedQuotePdfFile(elements.quotePdfFile.files?.[0] || null);
});

if (elements.quotePdfDropZone) {
  ["dragenter", "dragover"].forEach((eventName) => {
    elements.quotePdfDropZone.addEventListener(eventName, (event) => {
      event.preventDefault();
      elements.quotePdfDropZone.classList.add("is-drag-active");
    });
  });
  ["dragleave", "drop"].forEach((eventName) => {
    elements.quotePdfDropZone.addEventListener(eventName, (event) => {
      event.preventDefault();
      elements.quotePdfDropZone.classList.remove("is-drag-active");
    });
  });
  elements.quotePdfDropZone.addEventListener("drop", (event) => {
    const file = event.dataTransfer?.files?.[0] || null;
    if (!isPdfFile(file)) {
      const summary = document.querySelector("#quote-package-summary");
      if (summary) summary.textContent = "Only PDF files can be used for the quote package.";
      return;
    }
    setSelectedQuotePdfFile(file);
  });
}

// Multi-coil quote package: send the selected Direct Coil quote+drawing PDF to
// /api/package/quote, show the per-coil copper-strap price summary, and download
// the combined review-aid PDF (our drawing inserted after each coil's drawing).
document.querySelector("#build-quote-package")?.addEventListener("click", () => {
  buildQuotePackage().catch((error) => {
    const summary = document.querySelector("#quote-package-summary");
    if (summary) summary.textContent = error.message;
  });
});

async function buildQuotePackage() {
  const summary = document.querySelector("#quote-package-summary");
  const file = state.selectedQuotePdfFile;
  if (!isPdfFile(file)) {
    if (summary) summary.textContent = "Drop the Direct Coil quote+drawing PDF below first.";
    return;
  }
  if (summary) summary.textContent = "Building quote package…";
  const bytes = await file.arrayBuffer();
  // Build from the reviewed per-coil state so John's adjustments (and the reviewed
  // header count) drive pricing — not a blind re-extract of the PDF.
  const coils = state.pdfCoilPages
    .map((page) => {
      const td = (page.workflow || {}).template_drawing || {};
      const ex = td.extracted || {};
      return {
        tag: page.tag,
        coil_type: ex.coil_category || td.coil_category || null,
        our_svg: td.svg || null,
        header_count: ex.circuits ?? td.circuits ?? null,
      };
    })
    .filter((coil) => coil.tag);
  const body = { source_pdf_base64: arrayBufferToBase64(bytes) };
  if (coils.length) {
    body.coils = coils;
  }
  const result = await requestJson("/api/package/quote", {
    method: "POST",
    body: JSON.stringify(body),
  });
  const pkg = result.package || {};
  const lines = (result.coils || []).map((coil) => {
    const straps = coil.copper_straps || {};
    // Copper straps apply only to DX / HGRH — water coils (not_applicable) carry no
    // strap note at all, so list them without a copper-strap descriptor.
    if (straps.status === "not_applicable") {
      return `${coil.tag} (${coil.coil_type || "?"})`;
    }
    const label = straps.note || straps.status || "review required";
    const detail = straps.detail ? ` — ${straps.detail}` : "";
    return `${coil.tag} (${coil.coil_type || "?"}): ${label}${detail}`;
  });
  // Surface any coil that was NOT inserted loudly — a dropped coil must never read
  // as a silent success (e.g. a tag whose drawing page is missing from the source PDF).
  const warnings = (pkg.coils || [])
    .filter((coil) => coil.inserted === false)
    .map((coil) => {
      const reason = coil.not_inserted_reason || "not inserted";
      return `⚠ ${coil.tag} (${coil.coil_type || "?"}): ${reason}`;
    });
  if (summary) {
    summary.innerHTML =
      `<strong>${pkg.inserted_coil_count}/${result.coil_count} coil drawing(s) inserted</strong> &middot; `
      + `${pkg.source_page_count}→${pkg.page_count} pages &middot; review aid, watermarked<br>`
      + lines.map((line) => `<span class="quote-package-coil">${escapeHtml(line)}</span>`).join("<br>")
      + (warnings.length
        ? "<br>" + warnings.map((w) => `<span class="quote-package-warning">${escapeHtml(w)}</span>`).join("<br>")
        : "");
  }
  downloadBase64Pdf(pkg.pdf_base64, quotePackageExportName());
  // T3: the revised PDF is now downloaded — offer a pre-filled email draft. Prepare
  // only: mailto opens the user's mail client with To/Subject/Body ready; it never
  // sends and can't carry the attachment, so John attaches the downloaded file himself.
  const projectName =
    state.ui?.project?.project_name ||
    quotePackageExportName().replace(/_Revised\.pdf$/i, "");
  state.lastQuotePackage = {
    projectName,
    fileName: quotePackageExportName(),
    coilCount: result.coil_count ?? (result.coils || []).length,
    insertedCount: pkg.inserted_coil_count ?? null,
    tags: (result.coils || []).map((c) => c.tag).filter(Boolean),
    exceptionsK: state.lastProjectReview?.summary?.exceptions_K ?? null,
    // Keep the revised PDF so "Finalize deliverable" can file + attach it without rebuilding.
    revisedBase64: pkg.pdf_base64 || null,
  };
  const finalizeBtn = document.querySelector("#finalize-deliverable");
  if (finalizeBtn) finalizeBtn.hidden = false;
}

// Finalize deliverable — file the original quote + revised quote + auto-generated
// checklist into the project's DirectCoil folder and open a pre-filled Outlook DRAFT
// (revised PDF attached). Server-side (Outlook COM + SharePoint filing); never sends.
async function finalizeDeliverable() {
  const summary = document.querySelector("#quote-package-summary");
  const ctx = state.lastQuotePackage;
  if (!ctx || !ctx.revisedBase64) {
    if (summary) summary.textContent = "Build the quote package first.";
    return;
  }
  const submittal = state.selectedPdfFile;
  const quote = state.selectedQuotePdfFile;
  if (!isPdfFile(submittal) || !isPdfFile(quote)) {
    if (summary) summary.textContent = "Need both the analyzed submittal PDF and the quote PDF to finalize.";
    return;
  }
  if (summary) summary.textContent = "Finalizing deliverable — filing docs & drafting email…";
  const [subBytes, quoteBytes] = await Promise.all([submittal.arrayBuffer(), quote.arrayBuffer()]);
  const body = {
    submittal_pdf_base64: arrayBufferToBase64(subBytes),
    submittal_filename: submittal.name,
    quote_pdf_base64: arrayBufferToBase64(quoteBytes),
    quote_filename: quote.name,
    revised_pdf_base64: ctx.revisedBase64,
  };
  let res;
  try {
    res = await requestJson("/api/deliverable/finalize", {
      method: "POST",
      body: JSON.stringify(body),
    });
  } catch (err) {
    if (summary) summary.textContent = `Finalize failed: ${err.message || err}`;
    return;
  }
  const files = (res.files_written || [])
    .map((p) => `<span class="quote-package-coil">${escapeHtml(p)}</span>`)
    .join("<br>");
  const draft = res.draft_opened
    ? `<span class="quote-package-coil">Outlook draft opened — review &amp; send: <strong>${escapeHtml(res.subject)}</strong></span>`
    : `<span class="quote-package-warning">⚠ Draft not opened: ${escapeHtml(res.draft_status || "unknown")}</span>`;
  const chk =
    res.checklist_status && res.checklist_status !== "ok"
      ? `<br><span class="quote-package-warning">⚠ Checklist: ${escapeHtml(res.checklist_status)}</span>`
      : "";
  if (summary) {
    summary.innerHTML = `<strong>Filed to</strong> ${escapeHtml(res.folder)}<br>${files}<br>${draft}${chk}`;
  }
}

document.querySelector("#finalize-deliverable")?.addEventListener("click", finalizeDeliverable);

// NOTE: the "Verify Direct Coil entry" panel was unmounted pending completion of
// the read-and-alert feature; it will be re-added (correctly placed) in a later
// phase. The /api/direct-coil/verify route remains available for that work.

document.querySelector("#apply-draft")?.addEventListener("click", () => {
  elements.savedStatus.textContent = "Direct Coil draft refreshed from sanitized workflow";
});

document.querySelector("#update-drawing")?.addEventListener("click", () => {
  runWorkflowFromCurrentState().catch((error) => {
    elements.validationSummary.textContent = error.message;
  });
});

document.querySelector("#save-draft")?.addEventListener("click", () => {
  elements.savedStatus.textContent = "Save Draft is a Phase 2B review shell placeholder";
});

document.querySelector("#calculate-button")?.addEventListener("click", () => {
  elements.savedStatus.textContent = "Calculate is not implemented in this review shell";
});

// --- Theme (light/dark) toggle ---------------------------------------------
// The pre-paint script in index.html has already set data-theme on <html> from
// localStorage or the OS preference, so here we just sync the toggle UI and
// handle clicks. localStorage key: "coilforge-theme" ("light" | "dark").
const THEME_STORAGE_KEY = "coilforge-theme";

function applyTheme(theme) {
  const root = document.documentElement;
  const isDark = theme === "dark";
  if (isDark) {
    root.setAttribute("data-theme", "dark");
  } else {
    root.removeAttribute("data-theme");
  }
  const toggle = document.querySelector("#theme-toggle");
  const label = document.querySelector("#theme-toggle-label");
  const thumb = document.querySelector("#theme-toggle-thumb");
  if (toggle) toggle.setAttribute("aria-checked", String(isDark));
  if (label) label.textContent = isDark ? "Dark" : "Light";
  if (thumb) thumb.textContent = isDark ? "☾" : "☀";
}

function initThemeToggle() {
  // Single source of truth: whatever the pre-paint script already resolved.
  applyTheme(document.documentElement.getAttribute("data-theme") === "dark" ? "dark" : "light");

  const toggle = document.querySelector("#theme-toggle");
  if (toggle) {
    toggle.addEventListener("click", () => {
      const next = document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark";
      applyTheme(next);
      try {
        localStorage.setItem(THEME_STORAGE_KEY, next);
      } catch (e) {
        /* storage unavailable — theme still applies for this session */
      }
    });
  }

  // Follow OS changes only while the user has not made an explicit choice.
  if (window.matchMedia) {
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = (event) => {
      let stored = null;
      try {
        stored = localStorage.getItem(THEME_STORAGE_KEY);
      } catch (e) {
        stored = null;
      }
      if (!stored) applyTheme(event.matches ? "dark" : "light");
    };
    if (media.addEventListener) {
      media.addEventListener("change", onChange);
    } else if (media.addListener) {
      media.addListener(onChange);
    }
  }
}

initThemeToggle();

// --- Coil Checklist auto-fill (review aid) -------------------------------- //
function _checklistCell(value) {
  if (value === null || value === undefined || value === "") return "—";
  return escapeHtml(String(value));
}

function _verdictIcon(verdict) {
  return (
    { match: "✓", mismatch: "✗", missing_one: "·", both_missing: "—" }[verdict] || ""
  );
}

function renderChecklistSheet(sheet) {
  const inputs = (sheet.inputs || [])
    .map((i) => {
      const blank = i.value === null || i.value === undefined || i.value === "";
      return `<tr class="${blank ? "checklist-blank" : ""}">
        <td>${escapeHtml(i.label)}</td>
        <td>${_checklistCell(i.value)}</td>
        <td class="checklist-src">${escapeHtml(i.note || i.source || "")}</td></tr>`;
    })
    .join("");
  const comps = (sheet.comparisons || [])
    .map(
      (c) => `<tr class="checklist-${c.verdict}">
        <td>${escapeHtml(c.label)}</td>
        <td>${_checklistCell(c.coilforge)}</td>
        <td>${_checklistCell(c.checklist)}</td>
        <td class="checklist-verdict">${_verdictIcon(c.verdict)}</td></tr>`
    )
    .join("");
  return `<div class="checklist-sheet">
    <h4>${escapeHtml(sheet.tag)}
      <span class="subtle-label">${escapeHtml(sheet.category)} · ${sheet.mismatch_count} mismatch</span></h4>
    <div class="checklist-tables">
      <table class="checklist-table"><caption>Inputs written to column C</caption>
        <thead><tr><th>Field</th><th>Value</th><th>Source / note</th></tr></thead>
        <tbody>${inputs}</tbody></table>
      <table class="checklist-table"><caption>Dimensions — CoilForge engine vs Checklist formula</caption>
        <thead><tr><th>Dim</th><th>CoilForge</th><th>Checklist</th><th>=</th></tr></thead>
        <tbody>${comps}</tbody></table>
    </div></div>`;
}

function renderChecklistReview(review) {
  const root = document.querySelector("#checklist-fill-results");
  if (!root) return;
  if (!review || !review.sheets) {
    root.innerHTML = "";
    return;
  }
  const warnings = (review.warnings || []).length
    ? `<div class="checklist-warnings">⚠ ${review.warnings.map(escapeHtml).join("<br>⚠ ")}</div>`
    : "";
  root.innerHTML = warnings + review.sheets.map(renderChecklistSheet).join("");
}

async function fillCoilChecklist() {
  const file = state.selectedPdfFile || elements.pdfIntakeFile.files?.[0];
  const summary = document.querySelector("#checklist-fill-summary");
  if (!file) {
    if (summary) summary.textContent = "Analyze a submittal PDF above first.";
    return;
  }
  if (summary) summary.textContent = "Auto-filling the checklist in background… (opens Excel briefly)";
  try {
    const pdfBytes = await file.arrayBuffer();
    const review = await requestJson("/api/checklist/fill", {
      method: "POST",
      headers: {
        "Content-Type": "application/pdf",
        "X-CoilForge-Filename": sanitizeHeaderValue(file.name),
        ...coverPageHeader(),
      },
      body: pdfBytes,
    });
    renderChecklistReview(review);
    if (summary)
      summary.innerHTML =
        `Saved <strong>${escapeHtml(review.saved_path || "")}</strong> · ` +
        `${review.mismatch_total} dimension mismatch(es) to review · review aid, not exported`;
  } catch (error) {
    if (summary) summary.textContent = `Checklist fill failed: ${error.message || error}`;
  }
}

// Auto-fill toggle: default ON, persisted so John's OFF choice sticks across reloads.
const CHECKLIST_AUTO_KEY = "coilforge.checklistAutoFill";

function checklistAutoEnabled() {
  const toggle = document.querySelector("#checklist-auto-toggle");
  return toggle ? toggle.checked : true;
}

// Fired after every analyze (from hydratePdfWorkflow). Non-blocking, best-effort —
// a checklist/Excel failure never affects the analyze results already on screen.
function maybeAutoFillChecklist() {
  if (!checklistAutoEnabled()) return;
  if (!state.pdfCoilPages.length) return;
  fillCoilChecklist();
}

(function initChecklistAutoToggle() {
  const toggle = document.querySelector("#checklist-auto-toggle");
  if (!toggle) return;
  const stored = localStorage.getItem(CHECKLIST_AUTO_KEY);
  if (stored !== null) toggle.checked = stored === "1";
  toggle.addEventListener("change", () => {
    localStorage.setItem(CHECKLIST_AUTO_KEY, toggle.checked ? "1" : "0");
    // Re-checking is the manual trigger now that the button is gone: fill the
    // already-analyzed submittal right away (reuses the cached result server-side).
    if (toggle.checked) maybeAutoFillChecklist();
  });
})();

// Offline CCSI-export audit — drop the exported CCSI report PDF; CoilForge compares the
// dimensions CCSI printed against its own engine values (green/red), per coil, with NO
// live CCSI site and NO browser session. POSTs to /api/ccsi/audit-export, which reuses the
// SAME 0.01" comparator as the live /ccsi-compare path. Review aid only — never saves to CCSI.
async function auditCcsiExport(file) {
  const summary = document.querySelector("#ccsi-audit-summary");
  const results = document.querySelector("#ccsi-audit-results");
  if (!file) {
    return;
  }
  summary.textContent = "Auditing the CCSI export…";
  results.innerHTML = "";
  try {
    const pdfBytes = await file.arrayBuffer();
    const report = await requestJson("/api/ccsi/audit-export", {
      method: "POST",
      headers: {
        "Content-Type": "application/pdf",
        "X-CoilForge-Filename": sanitizeHeaderValue(file.name),
      },
      body: pdfBytes,
    });
    renderCcsiAudit(report);
  } catch (error) {
    summary.textContent = `CCSI export audit failed: ${error.message || error}`;
  }
}

function renderCcsiAudit(report) {
  const summary = document.querySelector("#ccsi-audit-summary");
  const results = document.querySelector("#ccsi-audit-results");
  const coils = (report && report.coils) || [];
  if (!coils.length) {
    summary.textContent = "No coils found in that PDF to audit.";
    results.innerHTML = "";
    return;
  }
  const totalMismatch = coils.reduce((n, c) => n + (c.mismatch_count || 0), 0);
  summary.innerHTML =
    `${coils.length} coil(s) audited · ` +
    `<strong>${totalMismatch}</strong> field(s) differ from CCSI · review aid, not exported`;
  results.innerHTML = coils.map(renderCcsiAuditCoil).join("");
}

function renderCcsiAuditCoil(coil) {
  const mismatch = coil.mismatch_count || 0;
  const allFields = coil.fields || [];
  // Only match/mismatch rows are actionable; a dimension CCSI's drawing didn't print is
  // "missing_one" — surfaced as a count (never silently dropped), not a red row.
  const rows = allFields
    .filter((f) => f.verdict === "match" || f.verdict === "mismatch")
    .map((f) => {
      const cls = f.verdict === "mismatch" ? "dc-control--mismatch" : "dc-control--match";
      const cf = f.coilforge === null || f.coilforge === undefined ? "—" : f.coilforge;
      const cc = f.ccsi === null || f.ccsi === undefined ? "—" : f.ccsi;
      const mark = f.verdict === "mismatch" ? "⚠ differ" : "✓ match";
      return (
        `<tr class="${cls}"><td>${escapeHtml(f.key)}</td>` +
        `<td>${escapeHtml(String(cf))}</td><td>${escapeHtml(String(cc))}</td>` +
        `<td>${mark}</td></tr>`
      );
    })
    .join("");
  const missing = allFields.filter((f) => f.verdict === "missing_one").length;
  const badge =
    mismatch > 0
      ? `<span class="ccsi-audit-badge has-mismatch">⚠ ${mismatch} differ</span>`
      : `<span class="ccsi-audit-badge">✓ all match</span>`;
  const missingNote = missing
    ? `<span class="ccsi-audit-note">${missing} not printed on the drawing</span>`
    : "";
  const body = rows
    ? `<table class="ccsi-audit-table"><thead><tr><th>Field</th><th>CoilForge</th><th>CCSI</th><th></th></tr></thead><tbody>${rows}</tbody></table>`
    : `<p class="ccsi-audit-empty">No printed dimensions to compare on this coil.</p>`;
  return (
    `<div class="ccsi-audit-coil"><h4>${escapeHtml(coil.tag || "Coil")} ` +
    `<span class="subtle-label">${escapeHtml(coil.coil_category || "")}</span> ${badge} ${missingNote}</h4>` +
    `${body}</div>`
  );
}

// Project Review — exceptions first. Analyze EVERY coil at once and show only the coils
// whose independent computations disagree (engine vs checklist = must-agree exception;
// engine vs CCSI = documented override). K (coils needing eyes) tracks problems, not coil
// count — so a clean 50-coil project reviews as fast as one coil. POSTs to
// /api/review/project (engine always; X-CoilForge-Checklist adds the Excel cross-check).
async function runProjectReview() {
  const file = state.selectedPdfFile || elements.pdfIntakeFile.files?.[0];
  const summary = document.querySelector("#project-review-summary");
  const results = document.querySelector("#project-review-results");
  if (!file) {
    summary.textContent = "Analyze a submittal PDF above first.";
    return;
  }
  const withChecklist = document.querySelector("#project-review-checklist")?.checked;
  summary.textContent = withChecklist ? "Reviewing all coils… (opens Excel briefly)" : "Reviewing all coils…";
  results.innerHTML = "";
  try {
    const pdfBytes = await file.arrayBuffer();
    const headers = {
      "Content-Type": "application/pdf",
      "X-CoilForge-Filename": sanitizeHeaderValue(file.name),
      ...coverPageHeader(),
    };
    if (withChecklist) {
      headers["X-CoilForge-Checklist"] = "1";
    }
    const gate = await requestJson("/api/review/project", { method: "POST", headers, body: pdfBytes });
    state.lastProjectReview = gate;   // retained so the auto-email + accept-passing can read it
    renderProjectGate(gate);
  } catch (error) {
    summary.textContent = `Project review failed: ${error.message || error}`;
  }
}

// A2 — "Accept passing coils": mark every coil the gate cleared (verdict "pass") as reviewed,
// so the Build gate needs only the K exceptions handled. Exceptions/overrides are left for John.
function acceptPassingCoils() {
  const gate = state.lastProjectReview;
  if (!gate || !Array.isArray(gate.coils)) {
    return;
  }
  const passTags = new Set(gate.coils.filter((c) => c.verdict === "pass").map((c) => c.tag));
  let marked = 0;
  (state.pdfCoilPages || []).forEach((page, index) => {
    if (passTags.has(page.tag) && !state.reviewedCoils.has(index)) {
      state.reviewedCoils.add(index);
      marked += 1;
    }
  });
  renderCoilReviewNav();
  renderProjectTree(state.ui);
  updateQuoteGate();
  const btn = document.querySelector("#accept-passing-coils");
  if (btn) {
    btn.textContent = `Accepted ${marked} passing coil(s) ✓`;
    btn.disabled = true;
  }
}

document.querySelector("#accept-passing-coils")?.addEventListener("click", acceptPassingCoils);

function renderProjectGate(gate) {
  const summary = document.querySelector("#project-review-summary");
  const results = document.querySelector("#project-review-results");
  const s = gate.summary || {};
  const coils = gate.coils || [];
  const K = s.exceptions_K || 0;
  const banner = K > 0
    ? `<span class="pr-badge has-mismatch">⚠ ${K} of ${s.coils} coil(s) need review</span>`
    : `<span class="pr-badge">✓ all ${s.coils} coil(s) clear</span>`;
  const src = `engine${s.sources?.checklist ? " + checklist" : ""}${s.sources?.ccsi ? " + CCSI" : ""}`;
  const bits = [`sources: ${src}`];
  if (s.override_coils) {
    bits.push(`${s.override_coils} coil(s) with documented CCSI overrides`);
  }
  if ((s.common_exception_keys || []).length) {
    bits.push(`common gap: ${escapeHtml(s.common_exception_keys.join(", "))}`);
  }
  if (s.checklist_note) {
    bits.push(escapeHtml(s.checklist_note));
  }
  summary.innerHTML = `${banner} <span class="subtle-label">${bits.join(" · ")}</span>`;

  // Reveal the "Accept passing coils" action: one click marks every cleared coil reviewed
  // so the Build gate needs only the K exceptions handled (clicks N -> K).
  const passCount = coils.filter((c) => c.verdict === "pass").length;
  const acceptBtn = document.querySelector("#accept-passing-coils");
  if (acceptBtn) {
    acceptBtn.hidden = passCount === 0;
    if (passCount > 0) {
      acceptBtn.textContent = `Accept ${passCount} passing coil(s) as reviewed`;
      acceptBtn.disabled = false;
    }
  }

  // Only flagged coils are shown; passing coils collapse into the count above.
  const flagged = coils.filter((c) => c.verdict !== "pass");
  if (!flagged.length) {
    results.innerHTML = `<p class="pr-empty">Every coil's independent computations agree — nothing to review. Review aid, not exported.</p>`;
    return;
  }
  results.innerHTML = flagged.map(renderGateCoil).join("");
}

function renderGateCoil(coil) {
  const isException = coil.verdict === "exception";
  const badge = isException
    ? `<span class="pr-badge has-mismatch">⚠ needs review</span>`
    : `<span class="pr-badge pr-badge--override">override</span>`;
  const exRows = (coil.exceptions || []).map((e) => {
    const detail = e.reason === "engine_vs_checklist"
      ? `engine ${escapeHtml(String(e.engine))} &ne; checklist ${escapeHtml(String(e.checklist))}`
      : escapeHtml(e.detail || "review required");
    return `<li><strong>${escapeHtml(e.key)}</strong> — ${detail}</li>`;
  }).join("");
  const ovRows = (coil.overrides || []).map((o) =>
    `<li><strong>${escapeHtml(o.key)}</strong> — CoilForge ${escapeHtml(String(o.engine))} vs CCSI ${escapeHtml(String(o.ccsi))}${o.acknowledged ? " (accepted)" : ""}</li>`
  ).join("");
  return `<div class="pr-coil ${isException ? "pr-coil--exception" : "pr-coil--override"}">
    <h4>${escapeHtml(coil.tag || "Coil")} ${badge}</h4>
    ${exRows ? `<ul class="pr-list pr-list--exception">${exRows}</ul>` : ""}
    ${ovRows ? `<ul class="pr-list pr-list--override">${ovRows}</ul>` : ""}
  </div>`;
}

document.querySelector("#run-project-review")?.addEventListener("click", () => {
  runProjectReview();
});

document.querySelector("#ccsi-audit-file")?.addEventListener("change", (event) => {
  const file = event.target.files?.[0];
  const nameEl = document.querySelector("#ccsi-audit-file-name");
  if (nameEl) {
    nameEl.textContent = file ? file.name : "No file selected";
  }
  if (file) {
    auditCcsiExport(file);
  }
});

// Bootstrap: always seed state.ui with the demo first (workflowToUiState spreads
// the previous ui state), then honor a ?case=PRC-N deep link from the PO Release
// board by pre-analyzing that case's submittal PDF.
const brainCaseParam = (new URLSearchParams(window.location.search).get("case") || "").trim();
loadDefaultDemoWorkflow()
  .then(() => {
    if (brainCaseParam) {
      return runWorkflowFromCase(brainCaseParam);
    }
    return undefined;
  })
  .catch((error) => {
    document.body.innerHTML = `<main class="load-error"><pre>${error.message}</pre></main>`;
  });

ensureProductOptions();
