const state = {
  ui: null,
  defaultInput: null,
  activeTab: "checklist",
  supplier: "direct_coil",
  ambientBaselineFile: null,
  ambientReturnFile: null,
  ambientMode: "compare",
  ambientSubmittalFile: null,
  ambientEzFile: null,
  // Gates the quote-request export: true only while a rendered package is on screen, so the
  // button can never post a submittal that produced no coils.
  ambientPackageReady: false,
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
  // Coil Checklist comparison, indexed for the Drawing Parameters panel:
  //   Map<coil tag, Map<engine slot id, comparison row>>
  // Keyed by TAG so one coil's verdicts can never colour another's rows — the bug
  // ccsiVerdictsByTag below now also avoids. Keyed by SLOT inside, because the panel's
  // key and the checklist's label disagree about which dimension they name (the panel's
  // logical O2 is the sheet's O4), and a name join would flag the wrong row.
  checklistBySlot: null,
  // True while a re-fill is queued/in flight after a manual correction. A row is only
  // treated as stale on THIS explicit signal — never by comparing the two CoilForge
  // numbers, which can differ permanently (the checklist resolves its own product line).
  checklistRefillPending: false,
  // CCSI compare verdicts, per coil tag. Was a flat object, so switching coils carried
  // the previous coil's green/red until the next Compare click.
  ccsiVerdictsByTag: {},
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
  manualParamActions: document.querySelector("#manual-param-actions"),
  manualParamReason: document.querySelector("#manual-param-reason"),
  manualParamApply: document.querySelector("#manual-param-apply"),
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
    // Leaving Wet Bulb was calculated-panel-only until 2026-07-28. It is a duty point John
    // checks against the application engineer's selection, and the calculated panel carries no
    // status class (so it can't be highlighted) — moved here for parity with the condensing
    // mirror. It is a MOVE, not a copy: the airCalculated entry below was removed.
    ["Leaving Wet Bulb(°F)", "input"],
    ["Total Capacity(MBH)(Per Coil)", "input"],
  ],
  airCalculated: [
    ["Standard Face Velocity", "Face Velocity(FPM)"],
    ["Entering Dry Bulb", "Entering Dry Bulb(°F)"],
    ["Entering Wet Bulb", "Entering Wet Bulb(°F)"],
    ["Leaving Dry Bulb", "Leaving Dry Bulb(°F)"],
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
  // uiState is threaded so the fallback layer and the mirror layer agree on coil format
  // (both consult directCoilMirrorFormat) — a tag-only-known RHHGRC-1 classifies the same way
  // in both, instead of the fallbacks silently disagreeing with the form being rendered.
  addCandidateFallbackFields(fieldsByLabel, activePdfCandidate(), uiState);
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

function activePdfCoilPage() {
  return state.pdfCoilPages[state.activePdfCoilPageIndex] || null;
}

function activePdfCandidate() {
  return activePdfCoilPage()?.workflow?.candidates?.[0] || null;
}

// The company-rule fallbacks below were DX-only until 2026-07-28, which left a condensing
// (RHHGRC/HGRH) coil showing a wall of "unmapped". John's own hand-filled transcriptions —
// examples/mapping_lab/case_004 (DX), case_005 (HGRH) and case_006 (one of each) — carry
// IDENTICAL values for the construction rules on both coil types, so the shared set is
// evidence-backed rather than assumed. Widened to CWC/HWC/PHWC on 2026-07-28 by John's
// decision: the water seeds carry no construction fields (so they neither confirm nor
// contradict), and leaving a real water coil as a wall of "unmapped" was the worse of the
// two errors — every value here renders review_required and an extracted value still wins.
function addCandidateFallbackFields(fieldsByLabel, candidate, uiState) {
  if (!candidate) {
    return;
  }
  const dxCandidate = isDxPdfCandidate(candidate);
  // isDxPdfCandidate is KEPT as the DX gate rather than replaced by a format check:
  // directCoilMirrorFormat falls through to "dx" as a catch-all, so a format-only gate would
  // hand drain-pan and DX-distributor values to any coil it failed to classify. Widening by
  // OR-ing in exactly the one evidenced format leaves the DX path byte-identical.
  const mirrorFormat = directCoilMirrorFormat(uiState);
  const condensingCandidate = !dxCandidate && mirrorFormat === "condensing";
  // Water coils (John 2026-07-28, 2949 Ferguson Theatre HWC): a SEPARATE predicate, not a
  // widening of condensingCandidate — that one also drives addCondensingDefaultFallbackFields
  // at the end of this function, which injects refrigerant conditions. Stamping evaporating
  // / condensing / subcooling temperatures onto a water coil would be inventing engineering
  // values, so the two predicates must stay distinct.
  const waterCandidate =
    !dxCandidate
    && ["chilled_water", "hot_water", "pre_hot_water", "post_hot_water"].includes(mirrorFormat);
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
  } else if (condensingCandidate) {
    // Shared subset only — no drain pan (absent from both HGRH seeds), no DX distributor,
    // no derived System Type (case_006's RHHGRC-1 is "Dual-Circuit Face Split", which the
    // connections-per-header derivation cannot produce).
    addSharedConstructionFallbackFields(fieldsByLabel, candidate);
    addSharedAirFallbackFields(fieldsByLabel, candidate);
    addSharedFoulingFallbackFields(fieldsByLabel);
  } else if (waterCandidate) {
    // Construction rules only + the EXTRACTED air subset. Deliberately NOT
    // addSharedAirFallbackFields: its two review defaults would overwrite the water coil's
    // real Max Coil Performance readings (capacity -> 0, Air Vel -> the computed value).
    addSharedConstructionFallbackFields(fieldsByLabel, candidate);
    addExtractedAirFallbackFields(fieldsByLabel, candidate);
    addSharedFoulingFallbackFields(fieldsByLabel);
    addWaterFeedsFallbackField(fieldsByLabel);
  }
  addUndefinedCoilHandField(fieldsByLabel);
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
    // Leaving air = the coil's "Max Coil Performance" DB/WB (John 2026-07-22). Wired here in
    // the coil-agnostic fallback (not just the DX helper) so the condensing (HGRH/RHHGRC) and
    // water mirrors also surface it whenever extracted; a reheat coil reports DB only (no WB),
    // which stays honestly blank rather than invented.
    [candidate.airside_conditions, "leaving_dry_bulb_f", ["Leaving Dry Bulb(°F)", "Leaving Dry Bulb"]],
    [candidate.airside_conditions, "leaving_wet_bulb_f", ["Leaving Wet Bulb(°F)", "Leaving Wet Bulb"]],
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
  // ORDER IS LOAD-BEARING: these run AFTER the fallbackMap above, using addDcFieldAlias (which
  // only writes when the existing entry has no mapped value). Run BEFORE it, the default would
  // claim the slot first and addDcFieldAlias would then REJECT the genuinely extracted value —
  // silently masking submittal data with a company default. Do not hoist this call.
  if (condensingCandidate) {
    addCondensingDefaultFallbackFields(fieldsByLabel);
  }
}

// When the submittal states no handing the backend flags the drawing `coil_hand_defaulted`
// and the frozen drawing path falls back to LH artwork so a review aid still renders.
//
// This row must NOT repeat that fallback as if it were data (John 2026-07-29). Printing
// "LH" here asserts a hand nobody read — and a wrong hand mirrors the entire coil, so it
// is the one field where a plausible-looking default is worse than an obvious blank. The
// row reads "not defined"; the banner above the drawing says which artwork was used and
// offers the LH/RH lever.
//
// Also replaces the bare "review required" this row showed before: that came from the
// blocked draft field and told the engineer nothing about WHY it was empty.
//
// addDcFieldAlias (add-only) so a coil whose handing WAS read keeps its real value.
const DC_COIL_HAND_UNDEFINED = "not defined";

function addUndefinedCoilHandField(fieldsByLabel) {
  const td = activePdfCoilPage()?.workflow?.template_drawing;
  if (!td || !td.coil_hand_defaulted) {
    return;
  }
  addDcFieldAlias(
    fieldsByLabel,
    "Coil Hand",
    directCoilReviewField(
      "coil_hand",
      DC_COIL_HAND_UNDEFINED,
      td.coil_hand_review || "Coil hand was not stated in the submittal — set it before use.",
      "coil_hand_not_stated",
    ),
  );
}

// An Oxygen8 water-coil detail box states "Circuits:" but has no "Total Feeds:" row, so
// Number Of Feeds read unmapped. The BACKEND already derives it (
// submittal_to_drawing._template_header_context_from_candidate falls back feeds = circuits
// for CWC/HWC) and exposes it as template_header_context.feeds — read THAT rather than
// re-deriving from geometry.circuits here, so there is one implementation to keep correct.
// Uses addDcFieldAlias (add-only): a submittal that DOES state Total Feeds still wins.
function addWaterFeedsFallbackField(fieldsByLabel) {
  const feeds = activePdfCoilPage()?.workflow?.template_header_context?.feeds;
  if (feeds === undefined || feeds === null || feeds === "") {
    return;
  }
  const field = directCoilReviewField(
    "number_of_feeds_total",
    feeds,
    "Derived from the submittal's Circuits (a water-coil box states no Total Feeds); confirm before use.",
    "water_coil_circuits_to_number_of_feeds",
  );
  ["Number Of Feeds(Total)", "Number Of Feeds"].forEach((label) => {
    addDcFieldAlias(fieldsByLabel, label, field);
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

// DX entry point. KEPT under this exact name — tests/test_phase2e_pdf_coil_intake.py asserts
// it as a substring, and those guards are the only automated coverage this path has.
function addDxOptionsFallbackFields(fieldsByLabel, candidate) {
  addSharedConstructionFallbackFields(fieldsByLabel, candidate);
  addDxOnlyOptionsFallbackFields(fieldsByLabel, candidate);
}

// Construction rules confirmed IDENTICAL on DX and HGRH/condensing coils by John's own
// transcriptions: examples/mapping_lab/case_004 (CDXC-1), case_005 (RHHGRC-1) and case_006
// (one of each). Every value below matches on all four coils.
//
// OVERWRITE SEMANTICS: these use setDcFieldAlias (unconditional Map.set) and run BEFORE the
// fallbackMap in addCandidateFallbackFields, so a company rule here WINS over an extracted
// submittal value. That is deliberate for "Casing Style" (both HGRH seeds say Standard), and
// it is the same behaviour DX has always had — but it is now applied to a second coil type,
// so it is stated rather than inherited silently.
function addSharedConstructionFallbackFields(fieldsByLabel, candidate) {
  const tubeMaterialField = directCoilTubeMaterialField(candidate);
  if (tubeMaterialField) {
    setDcFieldAlias(fieldsByLabel, "Tube Material", tubeMaterialField);
  }
  const sharedNote = "Direct Coil company rule (confirmed on DX and HGRH seeds); review before use.";
  const optionRules = [
    ["Header Material", "Copper", sharedNote],
    ["Header Wall Schedule", "(L)", sharedNote],
    ["Connection Material", "Copper", sharedNote],
    ["Connection Type", "Sweat", sharedNote],
    ["Casing Style", "Standard", sharedNote],
    // The seeds transcribe this as "Galvanized Steel"; John confirmed 2026-07-28 that the real
    // CCSI dropdown option carries the gauge. Do not "fix" this to match the seeds.
    ["Casing Material", "Galvanized Steel 16 gauge", sharedNote],
    ["Connection Ends", "Same End Only", sharedNote],
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
}

// DX-only. Drain pan is absent from BOTH HGRH seeds and the condensing mirror has no drain-pan
// rows at all. System Type is derived from connections-per-header, which case_006's RHHGRC-1
// ("Dual-Circuit Face Split") disproves for condensing — so it stays here, not in the shared set.
function addDxOnlyOptionsFallbackFields(fieldsByLabel, candidate) {
  const dxOnlyRules = [
    ["Drain Pan Type", "None", "Direct Coil company rule for DX PDF review."],
    ["Drain Pan Material", "SST", "Direct Coil company rule for DX PDF review."],
  ];
  dxOnlyRules.forEach(([label, value, notes]) => {
    setDcFieldAlias(fieldsByLabel, label, directCoilCompanyRuleField(normalizeDcLabel(label), value, notes));
  });
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

// DX entry point. KEPT under this exact name — pinned by tests/test_phase2e_pdf_coil_intake.py.
function addDxAirFallbackFields(fieldsByLabel, candidate) {
  addSharedAirFallbackFields(fieldsByLabel, candidate);
}

// Coil-agnostic: airflow dual-write, face velocity, RH and leaving WB are all pure
// arithmetic or straight passthrough of an extracted value. Face velocity is confirmed exact
// on both condensing seeds (case_005 2000/((26x25)/144)=443.08, case_006 5825/((26x72)/144)=448.08).
//
// OVERWRITE SEMANTICS: "Total Capacity(MBH)(Per Coil)" -> 0 below is an unconditional
// setDcFieldAlias running before the fallbackMap, so it MASKS the extracted
// performance.total_capacity_mbh (hasMappedDcValue treats 0 as a mapped value, so the later
// addDcFieldAlias refuses to replace it). That is why the DX mirror reads "0" today. It is
// intentional — John fills 0 by hand on all four seeds because Direct Coil's software owns
// final capacity — and it now applies to condensing too. Stated, not inherited by accident.
function addSharedAirFallbackFields(fieldsByLabel, candidate) {
  addExtractedAirFallbackFields(fieldsByLabel, candidate);
  addDxReviewDefaultAirFields(fieldsByLabel, candidate);
}

// The subset that only RE-LABELS extracted submittal values (entering airflow -> the two
// Direct Coil airflow rows, leaving WB, entering RH). Safe for any coil type because it
// invents nothing and masks nothing that was not already the same reading. Water coils get
// THIS and not the two review defaults below (John 2026-07-28).
function addExtractedAirFallbackFields(fieldsByLabel, candidate) {
  const airflowField = candidate.airside_conditions?.total_air_flow_cfm;
  if (airflowField) {
    const mappedAirflow = candidateFallbackField(airflowField, "total_air_flow_cfm", "pdf_entering_airflow_to_direct_coil_airflow");
    setDcFieldAlias(fieldsByLabel, "Total Air Flow(CFM)", mappedAirflow);
    setDcFieldAlias(fieldsByLabel, "Air Flow Per Coil(CFM)", mappedAirflow);
  }
  const relativeHumidityField = directCoilRelativeHumidityField(candidate);
  if (relativeHumidityField) {
    setDcFieldAlias(fieldsByLabel, "Entering Relative Humidity(%)", relativeHumidityField);
  }
  // Leaving air = the coil's "Max Coil Performance" DB/WB (John 2026-07-22). Leaving Dry Bulb
  // rides the paste surface already; the mirror's Leaving Wet Bulb has no paste field, so feed
  // it straight from the extracted candidate value (avoids churning the curated paste form).
  const leavingWetBulbField = candidate.airside_conditions?.leaving_wet_bulb_f;
  if (leavingWetBulbField) {
    setDcFieldAlias(
      fieldsByLabel,
      "Leaving Wet Bulb(°F)",
      candidateFallbackField(leavingWetBulbField, "leaving_wet_bulb_f", "pdf_max_coil_performance_wb_to_leaving_wet_bulb"),
    );
  }
}

// The two DX/condensing REVIEW DEFAULTS, kept out of the water path deliberately: both
// overwrite (setDcFieldAlias, before the fallbackMap), and on a water coil both would mask
// a genuinely extracted value now that the Max Coil Performance block is read — capacity
// 142.31 would render as 0, and the real Air Vel 424 would be replaced by the arithmetic
// 424.24. On DX/condensing they stay as-is: the computed face velocity matches the seeds
// exactly, and John types capacity 0 by hand on all four seeds because Direct Coil's
// software owns final capacity.
function addDxReviewDefaultAirFields(fieldsByLabel, candidate) {
  const faceVelocityField = directCoilFaceVelocityField(candidate);
  if (faceVelocityField) {
    setDcFieldAlias(fieldsByLabel, "Face Velocity(FPM)", faceVelocityField);
    setDcFieldAlias(fieldsByLabel, "Standard Face Velocity", faceVelocityField);
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

// HGRH/condensing review defaults approved by John 2026-07-28. Both hand-filled HGRH seeds
// (case_005 and case_006 coil 2) carry these BYTE-IDENTICAL values, while the DX coil in the
// same case_006 file carries entirely different, submittal-derived ones — so these are typed
// company defaults, not extracted data.
//
// MUST be called AFTER the fallbackMap loop and MUST use addDcFieldAlias (add-if-absent), so a
// submittal that DOES state a condensing temperature wins over the 115 default. Using
// setDcFieldAlias here, or calling this earlier, would silently mask real extracted data.
function addCondensingDefaultFallbackFields(fieldsByLabel) {
  const seedNote =
    "HGRH review default (both hand-filled HGRH seeds agree); confirm before use — " +
    "an extracted submittal value always wins over this.";
  // Each entry lists EVERY label the mirror might look the value up under. The Saturated
  // Suction row declares a sourceLabel of "Evaporating Temperature(°F)" (renderDcInputRows
  // resolves sourceLabel, not the display label), so registering the default under the
  // display label alone left the row unmapped — caught in the browser, invisible to the
  // source-level tests. Same alias pair the coil-agnostic fallbackMap already uses.
  const defaults = [
    [
      ["Evaporating Temperature(°F)", "Saturated Suction Temperature(°F)"],
      "saturated_suction_temperature_f",
      45,
    ],
    [["Suction Temperature at Compressor(°F)"], "suction_temperature_at_compressor_f", 68],
    [["Vapor Temperature(°F)"], "vapor_temperature_f", 140],
    [["Condensing Temperature(°F)"], "condensing_temperature_f", 115],
    [["Subcooling(°F)"], "subcooling_f", 18],
    // "Calculate" is a literal CCSI dropdown option meaning "let Direct Coil size it".
    [["Supply Connection Size"], "supply_connection_size", "Calculate"],
    [["Return Connection Size"], "return_connection_size", "Calculate"],
  ];
  defaults.forEach(([labels, key, value]) => {
    labels.forEach((label) => {
      addDcFieldAlias(
        fieldsByLabel,
        label,
        directCoilCompanyRuleField(key, value, seedNote, "direct_coil_hgrh_review_default"),
      );
    });
  });
}

// DX entry point. KEPT under this exact name — pinned by tests/test_phase2e_pdf_coil_intake.py.
function addDxRefrigerantAndFoulingFallbackFields(fieldsByLabel) {
  addDxOnlyRefrigerantFallbackFields(fieldsByLabel);
  addSharedFoulingFallbackFields(fieldsByLabel);
}

// DX-only: a condensing coil has no distributor, and the condensing mirror has no such row.
function addDxOnlyRefrigerantFallbackFields(fieldsByLabel) {
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
}

// Air side fouling factor is 0 on all four seeds, DX and HGRH alike.
function addSharedFoulingFallbackFields(fieldsByLabel) {
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
          // No default: case_006's RHHGRC-1 is "Dual-Circuit Face Split", so "Single-Circuit"
          // was wrong on a real coil, and the connections-per-header derivation cannot produce
          // "Face Split" either. Stays honestly unmapped until a rule is confirmed (John
          // 2026-07-28). Removed together with the renderDcInputRow fallback fix above, which
          // would otherwise have made this dead default suddenly live.
          ["System Type", "select"],
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
        ["Leaving Wet Bulb(°F)", "input"],
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
        // The 3rd tuple element is a sourceLabel, and this row used to carry
        // "Liquid Temperature(°F)" — so it looked up the LIQUID temp and displayed it under a
        // "Condensing" label, with no Liquid row on this mirror to contradict it (John
        // 2026-07-28). condensing_temp_f is registered under its own label in the coil-agnostic
        // fallbackMap, so the correct fix is to drop the alias, not to re-point it.
        ["Condensing Temperature(°F)", "input"],
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
        // Chilled water dehumidifies -> leaving WB is meaningful; hot water is sensible-only
        // (no leaving WB in source), so gate it exactly like the entering WB row above.
        ...(isHotWater ? [] : [["Leaving Wet Bulb(°F)", "input"]]),
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

// The two duty-point rows highlighted across every mirror (DX / condensing / water).
// Deliberately Leaving only: the submittal's "Max Coil Performance" DB/WB IS the leaving air,
// which is the number John checks the application engineer's selection against.
//
// BOTH spellings are listed on purpose. normalizeDcLabel strips punctuation but keeps the unit
// letter, so "Leaving Dry Bulb(°F)" -> "leavingdrybulbf" while the calculated panel's bare
// "Leaving Dry Bulb" -> "leavingdrybulb" — different keys. Listing only the (°F) form is what
// left the calculated panel unhighlighted (John 2026-07-29).
const DC_DUTY_HIGHLIGHT_LABELS = new Set(
  [
    "Leaving Dry Bulb(°F)",
    "Leaving Wet Bulb(°F)",
    "Leaving Dry Bulb",
    "Leaving Wet Bulb",
  ].map(normalizeDcLabel),
);

// dcCalculatedValue / dcControlValue return these sentinel strings instead of a number when
// nothing was derived. A duty point that does not exist must NOT be highlighted — same rule
// the input rows follow via `status !== "unmapped"`.
const DC_NON_VALUES = new Set([
  "unmapped", "review required", "calculated", DC_COIL_HAND_UNDEFINED, "",
]);

function isDcDutyLabel(label) {
  return DC_DUTY_HIGHLIGHT_LABELS.has(normalizeDcLabel(label));
}

function renderDcInputRow(label, controlType, field, fallbackValue = null) {
  const fixedValue = fixedDcDrawingValue(label);
  // A declared fallbackValue applies whenever the row has no USABLE value — not only when the
  // field is absent. The 52-field paste surface always emits a field (often status="unmapped"),
  // so keying off `field` alone made every declared default dead and rendered the literal
  // string "unmapped" instead (John 2026-07-28). A fallback is never "ready": it is a review
  // default, so it enters as review_required.
  const fieldValue = field ? dcControlValue(field) : null;
  // A BLOCKED field renders the literal string "review required" (dcControlValue), which
  // is not a value — so on a row that declares a default it must lose to that default,
  // exactly like "unmapped" does. Without this, "Air Flow Direction" showed
  // "review required" on every coil: the draft's `airflow_direction` field is blocked for
  // all of them and its label ("Airflow direction") normalises onto this row, so the
  // declared "Horizontal" was permanently dead (John 2026-07-29). Rows with no declared
  // default are unaffected — a blocked field there still reads "review required".
  const fieldIsUsable =
    fieldValue !== null && fieldValue !== "unmapped" && fieldValue !== "review required";
  const useFallback = !fieldIsUsable && fallbackValue !== null;
  const value =
    fixedValue !== null
      ? fixedValue
      : fieldIsUsable
        ? fieldValue
        : useFallback
          ? fallbackValue
          : (fieldValue ?? "unmapped");
  const status =
    fixedValue !== null
      ? "review_required"
      : useFallback
        ? "review_required"
        : field?.status || "unmapped";
  // Leaving DB/WB is the "Max Coil Performance" duty point John compares against the
  // application engineer's selection, so it gets an accent the eye lands on instead of having
  // to hunt for it (John 2026-07-28). Gated on the row actually HAVING a value: a reheat coil
  // is sensible-only and reports no leaving WB, and an absent duty point must keep reading as
  // unmapped rather than becoming a highlighted empty box.
  const dutyClass = isDcDutyLabel(label) && status !== "unmapped" ? " dc-control--duty" : "";
  const className = `dc-control ${statusClass(status)}${dutyClass}`;
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
          // Leaving DB/WB gets the same duty accent here as on the input side (John 2026-07-29
          // circled this panel's Leaving Dry Bulb). This panel has no status class of its own,
          // so the "has a value" test is against the sentinel strings dcCalculatedValue emits.
          const duty =
            isDcDutyLabel(label) && !DC_NON_VALUES.has(String(value).trim().toLowerCase())
              ? " dc-calculated-row--duty"
              : "";
          return `
            <div class="dc-calculated-row${duty}">
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
  let ok = false;
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
      ok = true;
    } else {
      ok = fallbackCopyText(text);
    }
  } catch {
    // writeText rejects when the tab lost focus / transient activation expired — fall
    // back to execCommand, and REPORT failure honestly so a silently-empty clipboard is
    // never mistaken for a successful copy (that is the "Could not parse JSON" on the CCSI side).
    ok = fallbackCopyText(text);
  }
  elements.savedStatus.textContent = ok
    ? "Copied review-aid field value"
    : "Copy failed — clipboard blocked. Keep this tab focused and try again.";
  return ok;
}

function fallbackCopyText(text) {
  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.setAttribute("readonly", "readonly");
  textarea.style.position = "fixed";
  textarea.style.left = "-9999px";
  document.body.append(textarea);
  textarea.select();
  let ok = false;
  try {
    ok = document.execCommand("copy");
  } catch {
    ok = false;
  }
  textarea.remove();
  return ok;
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
      // RF/HF/CH carry ccsi_readonly:true in the map — the filler skips them (CCSI computes
      // them) instead of keying off live DOM readOnly, which is true for every field whose
      // enable checkmark is off.
      ccsi_readonly: mapEntry.ccsi_readonly === true,
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
    // Carried so the CCSI filler can set Apply Venting/Draining I/O Constraints ON for a
    // hot-gas-bypass coil only (OFF for every other). Same special_feature that drives
    // template selection — reused so the flag and the chosen drawing agree.
    hot_gas_bypass: uiState.template_drawing?.extracted?.special_feature === "HGBP",
    // The engine-assembled drawing notes (R-007/008/035/080/081), carried so John stops
    // re-typing them into CCSI's own Drawing Notes box (John 2026-07-28). Deliberately a
    // SEPARATE top-level key, not a 14th entry in `fields`: those are numeric dimensions with
    // a unit and a field-map selector, and the map's contract test rejects anything that isn't
    // a base or multi-header dimension key. Its selector WAS captured live on 2026-08-05
    // (`#DrawingNotes`), so the fill now lands as well as travels.
    drawing_notes: ccsiDrawingNotes(uiState),
    fields,
  };
}

function ccsiDrawingNotes(uiState) {
  // Notes are not in drawing_parameters.parameters (dimension-only) — they live on the
  // paste-ready surface as field #26. The key is `direct_coil_label`, NOT `label`.
  const field = (uiState.direct_coil_paste_ready?.fields || []).find(
    (entry) => entry.direct_coil_label === "Drawing Notes",
  );
  const value =
    field && field.value !== null && field.value !== undefined && field.value !== ""
      ? String(field.value)
      : null;
  return {
    ccsi_label: "Drawing Notes",
    value,
    status: value ? field.status || "review_required" : "blocked",
    type: "text",
    // Captured live off coil.ccsi.ie/Coils/Edit on 2026-08-05: a single `<input type=text>`
    // with id/name `DrawingNotes`, unique and editable.
    //
    // The old labelText fallback resolved to NOTHING, and the reason is worth keeping:
    // CCSI's own markup associates the label wrongly — `<label for="Drawing_Notes">` names
    // an id that does not exist on the page, while the input is `DrawingNotes` (no
    // underscore). So `label.control` is null and the strategy had no element to return.
    // The notes push has therefore been silently doing nothing, which is exactly the
    // failure `selector_verified: false` existed to advertise.
    //
    // The labelText entry is kept as a SECOND choice, not deleted: if CCSI ever repairs
    // the `for` attribute the id may move with it, and a fallback that only works after
    // the markup is fixed costs nothing today.
    selectors: [
      { strategy: "css", selector: "#DrawingNotes" },
      { strategy: "labelText", text: "Drawing Notes" },
    ],
    selector_verified: true,
    blocked_reason: value ? null : "No drawing notes assembled for this coil.",
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
  const verdicts = {};
  for (const row of report.fields || []) {
    verdicts[row.key] = row;
  }
  // Stored under the ACTIVE coil's tag: these verdicts describe the CCSI record for
  // this coil only, and the previous flat store kept them on screen after a coil switch.
  state.ccsiVerdictsByTag[activeCoilTag() || "__no_tag__"] = verdicts;
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
    ${renderNonCoilRowsExcluded(summary)}
    ${renderPdfCoilReviewPages(summary)}
  `;
}

function renderNonCoilRowsExcluded(summary) {
  const excluded = summary && summary.non_coil_rows_excluded;
  if (!Array.isArray(excluded) || excluded.length === 0) {
    return "";
  }
  // Shown, never silent. A row the coil-tag gate refused has to be visible with its
  // reason -- otherwise a wrongly-excluded coil looks identical to one the submittal
  // never listed, which is the exact ambiguity the gate exists to remove.
  const items = excluded
    .map((reason) => `<li>${escapeHtml(reason)}</li>`)
    .join("");
  return `
    <details class="non-coil-excluded" open>
      <summary>Non-coil rows excluded (${excluded.length})</summary>
      <ul>${items}</ul>
    </details>
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
      ${renderSpecEditPanel(templateDrawing)}
      ${templateDrawingPicker(templateDrawing)}
      ${renderManualFillPanel(templateDrawing)}
      ${distributorOrientationBanner(templateDrawing)}
      ${coilHandAssumedBanner(templateDrawing)}
      ${hgbpProductLineBanner(templateDrawing)}
      ${headerCountConflictBanner(templateDrawing)}
      ${manualOverrideBanner(templateDrawing)}
      <div class="template-drawing-canvas">${templateDrawingBody(templateDrawing, rendered)}</div>
      ${renderThreeWayView(templateDrawing)}
      ${renderCaseNeighbors(templateDrawing)}
    </div>
  `;
  attachCoilDrawingPicker(templateDrawing);
  attachManualFillPanel(templateDrawing);
  attachSpecEditPanel(templateDrawing);
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

// Every analyzed coil's tag + connection size, for the backend's drain-pan pairing. Only
// data is shipped — which tag pairs with which stays in pdf_intake.drain_pan_partner_tag,
// the one place that knows the RHHGRC / RHHGRH / HGRC / HGRH spellings.
function siblingCoilsForPairing() {
  return (state.pdfCoilPages || [])
    .map((page) => {
      const ex = (page.workflow?.template_drawing || {}).extracted || {};
      const tag = ex.tag || page.tag;
      if (!tag) return null;
      return { tag, conn_size: ex.return_conn_size ?? null };
    })
    .filter(Boolean);
}

// Build the /api/coil-drawing/derive request body from a coil's extracted geometry
// plus the engineer's product/size pick and any human-in-the-loop manual fills. Manual
// engine inputs OVERRIDE the extracted spec value (a filled `rows` beats a blank/wrong
// extracted `rows`); param overrides + reason ride along for Tier-B + the audit log.
function deriveSpecFromTemplate(templateDrawing, productLine, unitSize, fills, candidate) {
  const ex = templateDrawing.extracted || {};
  const f = fills || {};
  const engineInputs = f.engineInputs || {};
  const pick = (key, fallback) =>
    engineInputs[key] !== undefined && engineInputs[key] !== "" ? engineInputs[key] : fallback;
  return {
    coil_category: ex.coil_category,
    // A manually picked hand must beat the extracted one: when the submittal states no
    // handing the frozen path silently defaults to LH, and the hand selects the LH vs RH
    // template — i.e. it mirrors the whole drawing. Hardcoding ex.hand here meant the
    // fill panel could offer the choice but the value never reached the backend.
    coil_hand: pick("coil_hand", ex.hand),
    circuits: pick("circuits", ex.circuits),
    special_feature: ex.special_feature,
    tag: ex.tag,
    rows: pick("rows", ex.rows),
    feeds: pick("feeds", ex.feeds),
    finned_height: ex.finned_height,
    finned_length: ex.finned_length,
    // Editable spec fields (Phase 2): an unlocked return conn / coating edit overrides the
    // extracted value so the engine recomputes (conn -> slots, coating -> R-080/081/035c notes).
    suction_conn_size: pick("return_conn_size", ex.return_conn_size),
    coating: pick("coating", ex.coating),
    product_type: productLine,
    unit_size: unitSize,
    // The three engine inputs the frozen path drops (un-gate levers).
    application: engineInputs.application,
    header_count: engineInputs.header_count,
    qty_conn_per_header: engineInputs.qty_conn_per_header,
    // NOT the lever above: the connections-per-header the SUBMITTAL stated, stamped by
    // analyze and round-tripped so the header-count conflict banner survives a re-derive
    // done for any unrelated reason. Cross-check input only — never an engine input.
    stated_qty_conn_per_header: templateDrawing.qty_conn_per_header_stated,
    // A DX paired with a reheat HGRH takes the engine's with-HGRH casing-depth branch
    // (CD 8.125, not 7.5 — and CD feeds the distributor spacing S). Analyze resolves the
    // partner across the sibling coils; /derive handles ONE coil and cannot see them, so
    // ship the siblings or the correction is lost on every manual fill. The PAIRING stays
    // server-side (drain_pan_partner_tag) — repeating the tag-alias table here would fork it.
    sibling_coils: siblingCoilsForPairing(),
    param_overrides: f.paramOverrides || [],
    // Phase 2 spec-field corrections (parallel capture channel; stage 'spec_field').
    spec_overrides: f.specOverrides || [],
    override_reason: f.reason,
    // Round-trip the submittal spec-panel values so the right-side panel stays
    // populated after the dimensions are logic-derived.
    panel: templateDrawing.panel,
    // Source candidate for the Direct Coil review-surface refresh (TR-9). /derive resolves
    // ONE coil from this spec and never sees the submittal, so it cannot rebuild the
    // paste-ready 52 fields on its own — without this the Drawing Notes and engine
    // dimensions stay frozen at analyze time. Same round-trip shape as `panel` /
    // `sibling_coils`; the backend re-validates it and checks its tag against `tag` above,
    // so a candidate from the wrong coil page is discarded rather than used.
    candidate,
    // Project identity so the coil_manual_fill milestone journals to the right case
    // and Case Retrieval can name the project. derive's result carries no
    // pdf_intake_summary, so the backend cannot recover these on its own.
    project_number: state.pdfIntakeSummary?.project_number,
    project_name: state.pdfIntakeSummary?.project_name,
  };
}

// Persist a re-derived result onto a PDF coil page so a page switch (which re-renders
// from page.workflow via workflowToUiState) reproduces the fills without re-hitting the
// engine. Also stashes the fills for re-apply after a full re-analyze. An explicit page
// is passed (never the shared active index) so a concurrent headless fan-out can't race.
function persistDerivedToPage(page, updated, fills, productLine, unitSize) {
  if (!page || !page.workflow) return;
  page.workflow.template_drawing = updated;
  if (updated.drawing_parameter_set) {
    page.workflow.drawing_parameter_set = updated.drawing_parameter_set;
  }
  // Direct Coil review surfaces refreshed by the re-derive (TR-9). They also ride along
  // nested inside `updated`, but `workflowToUiState` reads the OUTER keys — this copy is
  // the authoritative one, and without it a page switch re-renders the analyze-time values.
  if (updated.direct_coil_paste_ready) {
    page.workflow.direct_coil_paste_ready = updated.direct_coil_paste_ready;
    page.workflow.readiness_report = updated.readiness_report;
    page.workflow.direct_coil_input_draft = updated.direct_coil_input_draft;
  }
  if (fills && (Object.keys(fills.engineInputs || {}).length || (fills.paramOverrides || []).length)) {
    page.manualFills = { ...fills, productLine, unitSize };
  }
}

async function deriveCoilDrawing(templateDrawing, productLine, unitSize, fills, options) {
  const opts = options || {};
  // The candidate that rebuilds the Direct Coil review surfaces must be THIS coil's.
  // A headless re-analyze fan-out runs one derive per coil concurrently, so it reads the
  // explicitly targeted page — the shared active index would hand coil A's candidate to
  // coil B. An interactive fill is a click on the coil currently on screen, so the active
  // page is by definition the right one there (same assumption `targetPage` already makes).
  const candidate = opts.page
    ? opts.page.workflow?.candidates?.[0] || null
    : activePdfCandidate();
  const spec = deriveSpecFromTemplate(templateDrawing, productLine, unitSize, fills, candidate);
  if (elements.previewStatus && !opts.headless) {
    elements.previewStatus.textContent = "Deriving…";
  }
  try {
    const updated = await requestJson("/api/coil-drawing/derive", {
      method: "POST",
      body: JSON.stringify(spec),
    });
    // Headless (background re-apply) targets an explicit page; interactive persists to
    // the active page. Never rely on the shared active index during a concurrent fan-out.
    const targetPage = opts.page || state.pdfCoilPages[state.activePdfCoilPageIndex];
    persistDerivedToPage(targetPage, updated, fills, productLine, unitSize);
    if (opts.headless) {
      return updated;  // background re-apply: store only, caller re-renders the active coil once
    }
    // The re-derive rebuilt the Direct Coil review surfaces, so re-render the whole shell
    // from the persisted workflow: the paste table, the draft groups, the blocked-field
    // list and the header count chips all read those keys, and refreshing only some of
    // them would leave one panel showing analyze-time values next to another showing the
    // new ones. Runs BEFORE the drawing render below so the preview keeps the last word.
    if (updated.direct_coil_paste_ready && targetPage?.workflow) {
      renderShell(workflowToUiState(state.ui, targetPage.workflow, null));
    }
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
    const active = state.pdfCoilPages[state.activePdfCoilPageIndex];
    const fitInput = fitInputFromSpec(spec, active?.fit_inputs);
    if (active) {
      active.fit_inputs = fitInput;
      refreshMechanicalFit();
    } else {
      refreshMechanicalFit([fitInput]);
    }
    // The Coil Checklist is derived from the submittal, so a manual correction leaves it
    // stating the pre-override value until it is re-filled (John 2026-07-29).
    if (fills && (Object.keys(fills.engineInputs || {}).length || (fills.paramOverrides || []).length)) {
      scheduleChecklistRefill();
    }
    return updated;
  } catch (error) {
    if (opts.headless) throw error;  // let the fan-out aggregate the failure
    if (elements.drawingTemplateStatus) {
      elements.drawingTemplateStatus.innerHTML = `
        <strong>Could not derive dimensions</strong>
        <span>${escapeHtml(error.message)}</span>
      `;
    }
    return null;
  }
}

// Auto-surface "fill these to complete the drawing" panel (human-in-the-loop). The
// product/unit-size pickers are rendered by templateDrawingPicker above, so this panel
// shows only the OTHER fillable engine inputs + blocked drawing-param overrides.
function renderManualFillPanel(templateDrawing) {
  const plan = templateDrawing.manual_fill_plan;
  // Resolved BEFORE the early returns below: these carry the backend's skip reasons (e.g.
  // "coil tag missing - identity unverifiable, Direct Coil review fields not refreshed"),
  // and a withheld or plan-less coil is exactly when the engineer needs to be told why a
  // panel did not move. Returning early on those left the reason invisible.
  const errors = templateDrawing.manual_fill_errors || [];
  const errorHtml = errors.length
    ? `<div class="manual-fill-errors">${errors.map((e) => `<span>⚠ ${escapeHtml(e)}</span>`).join("")}</div>`
    : "";
  if (!plan) {
    return errorHtml ? `<div class="manual-fill-panel">${errorHtml}</div>` : "";
  }
  if (plan.withheld_reason) {
    return `
      <div class="manual-fill-panel is-withheld">
        <span class="manual-fill-title">Drawing withheld</span>
        <span class="manual-fill-hint">${escapeHtml(plan.withheld_reason)}</span>
        ${errorHtml}
      </div>`;
  }
  const items = (plan.items || []).filter(
    (it) => it.key !== "product_type" && it.key !== "unit_size",
  );
  if (!items.length && !errors.length) return "";
  const rows = items
    .map((it) => {
      const opts = it.allowed || [];
      let control;
      if (opts.length) {
        control = `<select data-manual-fill="${escapeHtml(it.key)}" data-fill-kind="${escapeHtml(it.kind)}">
            <option value="">—</option>
            ${opts.map((o) => `<option value="${escapeHtml(String(o))}">${escapeHtml(String(o))}</option>`).join("")}
          </select>`;
      } else {
        const isText = it.key === "application";
        control = `<input data-manual-fill="${escapeHtml(it.key)}" data-fill-kind="${escapeHtml(it.kind)}"
            data-unit="${escapeHtml(it.unit || "in")}" type="${isText ? "text" : "number"}" step="0.01"
            placeholder="${escapeHtml(String(it.current_value ?? ""))}" />`;
      }
      return `
        <label class="manual-fill-row">
          <span class="manual-fill-key">${escapeHtml(it.label)}</span>
          ${control}
          <span class="manual-fill-reason">${escapeHtml(it.reason)}</span>
        </label>`;
    })
    .join("");
  return `
    <div class="manual-fill-panel">
      <span class="manual-fill-title">Fill these to complete the drawing</span>
      ${rows}
      <label class="manual-fill-row">
        <span class="manual-fill-key">Reason</span>
        <input id="manual-fill-reason" type="text" placeholder="Why (required to log the change)" />
      </label>
      ${errorHtml}
      <button type="button" id="manual-fill-apply" class="manual-fill-apply">Apply &amp; complete drawing</button>
    </div>`;
}

function attachManualFillPanel(templateDrawing) {
  const applyBtn = document.querySelector("#manual-fill-apply");
  if (!applyBtn) return;
  applyBtn.addEventListener("click", () => submitManualFills(templateDrawing));
}

// True when the engineer actually changed a drawing-param value. Numeric compare with a
// 0.01 tolerance (mirrors the backend _match idea) so `8` vs the input string "8.0" is
// NOT a change — a naive !== would mark every field changed and fabricate an override +
// correction row per field on every Update click.
function drawingParamChanged(baselineValue, inputStr) {
  const a = numberOrFallback(String(baselineValue ?? ""), null);
  const b = numberOrFallback(inputStr, null);
  if (a === null || b === null) {
    return String(baselineValue ?? "").trim() !== String(inputStr ?? "").trim();
  }
  return Math.abs(a - b) > 0.01;
}

// "Update drawing" (Phase 1): collect the edited top-grid drawing-param inputs, diff them
// against the current resolved panel, and POST only the genuinely-changed keys as Tier-B
// param overrides through the single /derive endpoint. The response reflects the edit into
// the drawing (slot_values + SVG) and the ledger logs a (before -> after) correction.
async function submitDrawingParamOverrides(templateDrawing) {
  if (!templateDrawing) return;
  const reason = (elements.manualParamReason?.value || "").trim();
  const baseline = state.ui?.drawing_parameters?.parameters || {};
  const paramOverrides = [];
  document.querySelectorAll("#drawing-parameters [data-drawing-param]").forEach((el) => {
    const key = el.dataset.drawingParam;
    const raw = (el.value || "").trim();
    if (raw === "") return;
    const base = baseline[key];
    if (!drawingParamChanged(base ? base.value : null, raw)) return;
    const value = numberOrFallback(raw, null);
    if (value === null) return;
    paramOverrides.push({ key, value, unit: el.dataset.unit || "in", override_reason: reason });
  });
  if (!paramOverrides.length) {
    if (elements.drawingTemplateStatus) {
      elements.drawingTemplateStatus.innerHTML =
        `<strong>No changes</strong><span>Edit a value before updating the drawing.</span>`;
    }
    return;
  }
  if (!reason) {
    if (elements.drawingTemplateStatus) {
      elements.drawingTemplateStatus.innerHTML =
        `<strong>Reason required</strong><span>Enter a reason to log the manual override.</span>`;
    }
    return;
  }
  const productLine =
    document.querySelector("#coil-product-line")?.value || templateDrawing.product_type || "";
  const unitSize =
    document.querySelector("#coil-unit-size")?.value || templateDrawing.unit_size || "";
  await deriveCoilDrawing(templateDrawing, productLine, unitSize, {
    engineInputs: {}, paramOverrides, reason,
  });
}

// Show the "Update drawing" action row only when manual editing is unlocked.
function syncManualParamActions() {
  if (elements.manualParamActions) {
    elements.manualParamActions.hidden = !state.manualDrawingMode;
  }
}

const _MANUAL_NUMERIC_INPUTS = new Set([
  "header_count", "qty_conn_per_header", "rows", "feeds", "circuits",
]);

async function submitManualFills(templateDrawing) {
  const reason = (document.querySelector("#manual-fill-reason")?.value || "").trim();
  const engineInputs = {};
  const paramOverrides = [];
  document.querySelectorAll("[data-manual-fill]").forEach((el) => {
    const key = el.dataset.manualFill;
    const raw = (el.value || "").trim();
    if (raw === "") return;
    if (el.dataset.fillKind === "drawing_param") {
      const value = numberOrFallback(raw, null);
      if (value !== null) {
        paramOverrides.push({ key, value, unit: el.dataset.unit || "in", override_reason: reason });
      }
    } else {
      engineInputs[key] = _MANUAL_NUMERIC_INPUTS.has(key) ? numberOrFallback(raw, raw) : raw;
    }
  });
  if (paramOverrides.length && !reason) {
    if (elements.drawingTemplateStatus) {
      elements.drawingTemplateStatus.innerHTML =
        `<strong>Reason required</strong><span>Enter a reason to log the manual override.</span>`;
    }
    return;
  }
  // Current product/size come from the existing picker (or the already-derived drawing).
  const productLine =
    document.querySelector("#coil-product-line")?.value || templateDrawing.product_type || "";
  const unitSize =
    document.querySelector("#coil-unit-size")?.value || templateDrawing.unit_size || "";
  await deriveCoilDrawing(templateDrawing, productLine, unitSize, {
    engineInputs, paramOverrides, reason,
  });
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

// Phase 2 — the engine-relevant spec fields the engineer can feed/correct via a per-field
// lock. An edit re-derives (conn -> slots, coating -> notes) AND logs a (before -> after)
// correction. Mirrors web_app._KNOWN_SPEC_FIELD_KEYS; template-selection fields are excluded.
const SPEC_EDIT_FIELDS = [
  { key: "circuits", label: "Circuits", numeric: true },
  { key: "rows", label: "Rows", numeric: true },
  { key: "feeds", label: "Feeds", numeric: true },
  { key: "return_conn_size", label: "Return conn.", numeric: true },
  { key: "coating", label: "Coating", numeric: false },
];

function renderSpecEditPanel(templateDrawing) {
  const ex = templateDrawing.extracted || {};
  const rows = SPEC_EDIT_FIELDS.map((fld) => {
    const value = ex[fld.key];
    const shown = value === null || value === undefined || value === "" ? "—" : value;
    return `
      <div class="spec-edit-row" data-spec-field="${fld.key}" data-spec-numeric="${fld.numeric}" data-spec-prev="${escapeHtml(String(value ?? ""))}">
        <span class="spec-edit-label">${escapeHtml(fld.label)}</span>
        <span class="spec-edit-value">${escapeHtml(String(shown))}</span>
        <input class="spec-edit-input dc-control" type="${fld.numeric ? "number" : "text"}" step="0.01" value="${escapeHtml(String(value ?? ""))}" hidden />
        <input class="spec-edit-reason" type="text" placeholder="Reason (logged)" hidden />
        <button type="button" class="spec-edit-lock" aria-label="Unlock ${escapeHtml(fld.label)}">🔒</button>
        <button type="button" class="spec-edit-save manual-fill-apply" hidden>Save</button>
      </div>`;
  }).join("");
  return `<details class="spec-edit-panel"><summary>Spec data — lock/unlock to edit &amp; log</summary>${rows}</details>`;
}

function attachSpecEditPanel(templateDrawing) {
  document.querySelectorAll(".spec-edit-row").forEach((row) => {
    const lock = row.querySelector(".spec-edit-lock");
    const save = row.querySelector(".spec-edit-save");
    const input = row.querySelector(".spec-edit-input");
    const reason = row.querySelector(".spec-edit-reason");
    const valueSpan = row.querySelector(".spec-edit-value");
    if (!lock || !save || !input || !reason || !valueSpan) return;
    lock.addEventListener("click", () => {
      const locked = input.hidden;
      input.hidden = !locked; reason.hidden = !locked; save.hidden = !locked;
      valueSpan.hidden = locked;
      lock.textContent = locked ? "🔓" : "🔒";
      if (locked) input.focus();
    });
    save.addEventListener("click", () => submitSpecEdit(templateDrawing, row));
  });
}

async function submitSpecEdit(templateDrawing, row) {
  const field = row.dataset.specField;
  const numeric = row.dataset.specNumeric === "true";
  const prevRaw = row.dataset.specPrev;
  const raw = (row.querySelector(".spec-edit-input")?.value || "").trim();
  const reason = (row.querySelector(".spec-edit-reason")?.value || "").trim();
  const setStatus = (title, msg) => {
    if (elements.drawingTemplateStatus) {
      elements.drawingTemplateStatus.innerHTML = `<strong>${title}</strong><span>${msg}</span>`;
    }
  };
  if (raw === "") { setStatus("No value", "Enter a value before saving."); return; }
  if (!reason) { setStatus("Reason required", "Enter a reason to log the change."); return; }
  const newVal = numeric ? numberOrFallback(raw, null) : raw;
  if (newVal === null) { setStatus("Invalid number", `${field}: enter a number.`); return; }
  const prevVal = prevRaw === "" ? null : numeric ? numberOrFallback(prevRaw, prevRaw) : prevRaw;
  if (String(prevVal ?? "") === String(newVal)) { setStatus("No change", "Value is unchanged."); return; }
  const productLine =
    document.querySelector("#coil-product-line")?.value || templateDrawing.product_type || "";
  const unitSize =
    document.querySelector("#coil-unit-size")?.value || templateDrawing.unit_size || "";
  await deriveCoilDrawing(templateDrawing, productLine, unitSize, {
    engineInputs: { [field]: numeric ? newVal : raw },
    specOverrides: [
      { field_key: field, previous_value: prevVal, new_value: newVal, override_reason: reason },
    ],
    reason,
  });
}

// Phase 2b — three-way review table (submittal / CoilForge / engineer). Green cell = matches
// the column to its left; red = differs. A red Engineer cell is the correction signal (where
// the human diverged from the machine) — the raw material for mapping improvement.
function threeWayCell(value, verdict) {
  const cls =
    verdict === "match" ? "tw-match" : verdict === "mismatch" ? "tw-mismatch" : "";
  const shown = value === null || value === undefined || value === "" ? "—" : value;
  return `<td class="${cls}">${escapeHtml(String(shown))}</td>`;
}

function renderThreeWayView(templateDrawing) {
  const tw = templateDrawing.three_way;
  if (!tw || !Array.isArray(tw.fields) || !tw.fields.length) return "";
  const rows = tw.fields
    .map(
      (f) => `
      <tr>
        <td class="tw-field">${escapeHtml(String(f.field))}</td>
        ${threeWayCell(f.submittal, null)}
        ${threeWayCell(f.coilforge, f.submittal_vs_coilforge)}
        ${threeWayCell(f.engineer, f.coilforge_vs_engineer)}
      </tr>`,
    )
    .join("");
  return `
    <details class="three-way-panel">
      <summary>Three-way review — submittal vs CoilForge vs engineer</summary>
      <div class="three-way-scroll">
        <table class="three-way-table">
          <thead><tr><th>Field</th><th>Submittal</th><th>CoilForge</th><th>Engineer</th></tr></thead>
          <tbody>${rows}</tbody>
        </table>
      </div>
      ${tw.note ? `<p class="subtle-label">${escapeHtml(tw.note)}</p>` : ""}
    </details>`;
}

// Phase 2.1 — "past corrections" panel. Shows the nearest past coils to this one (masked-Gower
// over the capture ledger) and the corrections John made on them, as EVIDENCE. Read-only: it
// never applies a value or offers an action. Degrades silently when the corpus is empty /
// capture is off (case_neighbors.enabled === false or neighbors === []).
function caseNeighborVal(v) {
  return v === null || v === undefined || v === "" ? "—" : String(v);
}

function renderCaseNeighbors(templateDrawing) {
  const cn = templateDrawing.case_neighbors;
  if (!cn || cn.enabled === false) return "";
  const neighbors = Array.isArray(cn.neighbors) ? cn.neighbors : [];
  if (!neighbors.length) return "";
  const withCorr = neighbors.reduce(
    (n, x) => n + ((Array.isArray(x.corrections) && x.corrections.length) ? 1 : 0),
    0,
  );
  const badge = cn.insufficient_corpus
    ? ` <span class="subtle-label">· 코퍼스 ${cn.corpus_size}/${cn.corpus_min ?? "?"} — 참고용</span>`
    : "";
  const rows = neighbors
    .map((nb) => {
      const f = nb.features || {};
      const chips = ["coil_category", "product_line", "unit_size", "hand", "header_type"]
        .map((k) => f[k])
        .filter(Boolean)
        .map((v) => `<span class="cn-chip">${escapeHtml(String(v))}</span>`)
        .join("");
      const corr = Array.isArray(nb.corrections) ? nb.corrections : [];
      const corrHtml = corr.length
        ? corr
            .map(
              (c) =>
                `<li><span class="cn-field">${escapeHtml(String(c.field_key))}</span>: ` +
                `${escapeHtml(caseNeighborVal(c.before))} <span class="cn-arrow">→</span> ` +
                `<span class="cn-after">${escapeHtml(caseNeighborVal(c.after))}</span></li>`,
            )
            .join("")
        : `<li class="subtle-label">교정 이력 없음</li>`;
      const dimmed = corr.length ? "" : " cn-neighbor-empty";
      return `
        <div class="cn-neighbor${dimmed}">
          <div class="cn-neighbor-head">
            <span class="cn-tag">${escapeHtml(String(nb.tag ?? "—"))}</span>
            ${chips}
            <span class="subtle-label">d=${Number(nb.distance).toFixed(3)} · 공유축 ${escapeHtml(String(nb.shared_axes))}</span>
          </div>
          <ul class="cn-corrections">${corrHtml}</ul>
        </div>`;
    })
    .join("");
  return `
    <details class="case-neighbors-panel">
      <summary>이전 교정 · ${neighbors.length}개 유사 코일 (${withCorr}개 교정 이력)${badge}</summary>
      <div class="cn-body">${rows}</div>
      <p class="subtle-label">비슷한 과거 코일에서 John이 고친 값 — 참고용, 자동 적용 안 함.</p>
    </details>`;
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

// Loud review-required banner when the drawn hand was ASSUMED rather than read. The
// frozen drawing path falls back to LH when neither the cover row nor the as-built parse
// states a handing (Oxygen8 cover rows carry it for DX but leave it blank for water
// coils), and the hand selects the LH vs RH template — it mirrors the whole drawing. The
// value still renders; this says it is an assumption. See
// submittal_to_drawing._flag_defaulted_coil_hand.
function coilHandAssumedBanner(templateDrawing) {
  const warning = templateDrawing && templateDrawing.coil_hand_review;
  if (!warning || !templateDrawing.coil_hand_defaulted) {
    return "";
  }
  return `<div class="drawing-orientation-warning">⚠ ${escapeHtml(warning)}</div>`;
}

// Loud review-required banner when an HGBP drawing was produced without a resolved
// product line — hot gas bypass is a Nova / Ventum H option, so an unknown line leaves
// that premise unverified. Empty string when not flagged. See
// submittal_to_drawing._flag_hgbp_product_line_unverified.
function hgbpProductLineBanner(templateDrawing) {
  const warning = templateDrawing && templateDrawing.hgbp_product_line_warning;
  if (!warning) {
    return "";
  }
  return `<div class="drawing-orientation-warning">⚠ ${escapeHtml(warning)}</div>`;
}

// Loud review-required banner when the submittal states more connections per header than
// the circuit count we could read. Circuits IS the header count on the drawing path
// (header_type = "Header N"), and with nothing stating it the backend falls to 1 — a
// confidently single-header drawing built on no evidence (project 3095). The stated
// connection count is a DIFFERENT quantity, so it only raises the question here; it never
// answers it. See submittal_to_drawing._flag_header_count_conflict.
function headerCountConflictBanner(templateDrawing) {
  const warning = templateDrawing && templateDrawing.header_count_review;
  if (!warning || !templateDrawing.header_count_conflict) {
    return "";
  }
  return `<div class="drawing-orientation-warning">⚠ ${escapeHtml(warning)}</div>`;
}

// Loud marker when one or more dimensions were manually overridden (Phase 1 reflection):
// the drawing now shows an engineer-supplied value, not the machine proposal, so it must
// never read as an approved as-built. Driven by result.manual_override_keys; empty when
// no override was applied. See submittal_to_drawing._reflect_param_overrides_into_slots.
function manualOverrideBanner(templateDrawing) {
  const keys = templateDrawing && templateDrawing.manual_override_keys;
  if (!keys || !keys.length) {
    return "";
  }
  return `<div class="drawing-orientation-warning">✎ Manually overridden: ${escapeHtml(keys.join(", "))} — review aid, not approved</div>`;
}

function renderDrawingParameters(uiState) {
  const parameters = uiState.drawing_parameters?.parameters || {};
  // Stamp the coil's special feature onto the container so the CCSI userscript's
  // DOM-scraped "Send to CCSI" path can read HGBP (the clipboard path reads state directly).
  elements.drawingParameters.dataset.specialFeature =
    uiState.template_drawing?.extracted?.special_feature || "";
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
  syncManualParamActions();
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
  const ccsiForCoil = state.ccsiVerdictsByTag?.[activeCoilTag() || "__no_tag__"];
  const cmp = ccsiForCoil && ccsiForCoil[parameter.key];
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

  // Coil Checklist verdict for this same dimension, joined by SLOT (the panel's key and
  // the sheet's label name different dimensions — see DrawingParameter.slot). This is the
  // whole point of the feature: the disagreement is visible here instead of requiring a
  // scroll down to the comparison table and a mental line-up of two tables.
  const chk = checklistEntryFor(parameter);
  const chkView = checklistRowView(chk, parameter);

  // ONE border class wins, worst state first. `--empty` outranks everything because a
  // row with no value at all is a bigger problem than any disagreement about its value.
  // The unadjudicated checklist divergence outranks the CCSI one: a checklist mismatch
  // says CoilForge itself may be wrong, while a CCSI mismatch says an external form
  // disagrees with us. Green is CCSI's alone — two implementations agreeing is not
  // approval, and every value here stays review-required regardless.
  // An ADJUDICATED divergence (amber `--adjudicated`) arrives in the same slot: it is
  // still a statement about our own value, so it still outranks CCSI — it has simply
  // stopped being an open question and no longer competes with the red rows.
  const borderClass = emptyControl || chkView.controlClass || compareClass;

  // Badges stack (both spans already span the full row), so nothing is hidden by
  // something else. Order: why it's blank -> what the checklist says -> what CCSI says.
  const badges = [
    chkView.badge,
    mismatchBadge,
    reason ? `<span class="dc-dimension-reason">⚠ ${reason}</span>` : "",
  ]
    .filter(Boolean)
    .join("");

  // Tooltips join rather than override — the old code let a CCSI mismatch hide the
  // reason a field was blank.
  const titleAttr = [chkView.title, compareTitle, reason]
    .filter(Boolean)
    .join(" · ");
  // data-drawing-param / data-unit stay present in both modes so the derive
  // round-trip (collectDrawingPreviewValues) always finds the value; `readonly`
  // locks the field outside manual mode while keeping the Direct-Coil look.
  return `
    <label class="dc-dimension-row ${statusClass(parameter.status)}"${titleAttr ? ` title="${titleAttr}"` : ""}>
      <span>${escapeHtml(parameter.key)}</span>
      <input class="dc-dimension-check" type="checkbox" ${hasValue ? "checked" : ""} disabled />
      <input
        class="dc-control ${statusClass(parameter.status)}${borderClass}"
        data-drawing-param="${escapeHtml(parameter.key)}"
        data-unit="${escapeHtml(parameter.unit || "in")}"
        type="number"
        step="0.01"
        value="${parameter.value ?? ""}"
        ${titleAttr ? `title="${titleAttr}"` : ""}
        ${state.manualDrawingMode ? "" : "readonly"}
      />
      ${badges}
    </label>
  `;
}

// The checklist comparison row describing the SAME dimension as this panel row, or null.
// Joined on the backend-supplied slot id, never on the key/label (they disagree).
function checklistEntryFor(parameter) {
  if (!parameter.slot || !state.checklistBySlot) return null;
  const bySlot = state.checklistBySlot.get(activeCoilTag());
  return bySlot ? bySlot.get(parameter.slot) || null : null;
}

function _num(value) {
  return value === null || value === undefined || value === "" ? "—" : value;
}

// How one checklist verdict presents on a panel row: {controlClass, badge, title}.
//
// Red is spent carefully. Only an unexplained disagreement earns it — a structural
// absence or a decision John already made must not look like a defect, or the colour
// stops meaning anything.
function checklistRowView(entry, parameter) {
  const none = { controlClass: "", badge: "", title: "" };
  if (!state.checklistBySlot) return none;

  if (state.checklistRefillPending) {
    return {
      controlClass: "",
      badge: `<span class="dc-dimension-note">checklist re-running…</span>`,
      title: "Checklist is being re-filled with your correction",
    };
  }

  // No counterpart on this coil's sheet. Said out loud rather than left silent: on a
  // water sheet the panel's I row has no checklist twin (the sheet's single "I/O" row
  // maps to slot.O2, which is the panel's O), and an unmarked row reads as "agrees".
  if (!entry) {
    if (!parameter.slot || !state.checklistBySlot.has(activeCoilTag())) return none;
    return {
      controlClass: "",
      badge: `<span class="dc-dimension-note">no checklist counterpart on this sheet</span>`,
      title: "This dimension has no row on the coil's checklist sheet",
    };
  }

  const cf = _num(entry.coilforge);
  const cl = _num(entry.checklist);

  if (entry.verdict === "overridden") {
    const prev = entry.override && entry.override.previous_value;
    return {
      controlClass: "",
      badge: `<span class="dc-dimension-note">✎ overridden — sheet computed ${escapeHtml(String(_num(prev)))}</span>`,
      title: `Manual override; the sheet's own formula gave ${_num(prev)}`,
    };
  }

  if (entry.verdict === "missing_one") {
    return {
      controlClass: "",
      badge: `<span class="dc-dimension-note">checklist has no value for this dim</span>`,
      title: `Checklist ${cl} vs CoilForge ${cf}`,
    };
  }

  // An ADJUDICATED divergence. The backend attached this (review/divergence.py) — the
  // scope match (variant axis, exact-size-before-wildcard, delta band) is never
  // re-implemented here, or the two would drift on exactly the coils under investigation.
  //
  // Amber is only for a gap in the OTHER implementation. `known_defect` — "CoilForge is
  // wrong" — deliberately keeps its red: dimming an open defect of ours would hide the one
  // class of divergence that most needs fixing.
  const adj = entry.divergence;
  if (adj && adj.applies && adj.severity === "known_gap") {
    const stamp = adj.promoted ? adj.id : `${adj.id} · unpromoted`;
    return {
      controlClass: " dc-control--adjudicated",
      badge:
        `<span class="dc-dimension-adjudicated">◈ ${escapeHtml(stamp)} — ` +
        `checklist ${escapeHtml(String(cl))}, ours ${escapeHtml(String(cf))}</span>`,
      title: escapeHtml(
        `${adj.id} (${adj.verdict}${adj.promoted ? "" : ", not yet promoted"}): ` +
          `${adj.reason}` + (adj.note ? ` — ${adj.note}` : ""),
      ),
    };
  }
  if (adj && adj.severity === "re_escalated") {
    return {
      controlClass: " dc-control--divergence",
      badge:
        `<span class="dc-dimension-mismatch">⚠ ${escapeHtml(adj.id)} no longer covers ` +
        `this — checklist ${escapeHtml(String(cl))} &ne; CoilForge ${escapeHtml(String(cf))}</span>`,
      title: escapeHtml(adj.note || "This ruling no longer applies; re-adjudicate."),
    };
  }

  if (entry.verdict === "mismatch") {
    // `known_defect` falls through to here on purpose — it is still a real mismatch, and
    // the ruling only adds the explanation, not a downgrade.
    const known = adj && adj.severity === "known_defect"
      ? ` <span class="dc-dimension-note">${escapeHtml(adj.id)}: known CoilForge defect</span>`
      : "";
    return {
      controlClass: " dc-control--divergence",
      badge:
        `<span class="dc-dimension-mismatch">⚠ Checklist ${escapeHtml(String(cl))} ` +
        `&ne; CoilForge ${escapeHtml(String(cf))}</span>${known}`,
      title: escapeHtml(
        adj
          ? `${adj.id} (${adj.verdict}): ${adj.reason}`
          : `Checklist formula ${cl} vs CoilForge ${cf} — unadjudicated divergence`,
      ),
    };
  }

  // verdict === "match": deliberately no styling. Two independent implementations
  // agreeing is evidence, not approval, and the value stays review-required.
  return none;
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
        ${coilHandAssumedBanner(templateDrawing)}
        ${hgbpProductLineBanner(templateDrawing)}
        ${headerCountConflictBanner(templateDrawing)}
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
  // Capture any manual fills from the PRIOR analyze (keyed by tag) so a re-analyze of
  // the same PDF re-applies them instead of dropping them (findings C-NEW-1/H-NEW-2:
  // the workflow is PDF-bytes-memoized, so reproduction is a frontend /derive re-apply,
  // never a cached workflow re-run). Tag is primary; a coil can reorder across analyses.
  const priorFillsByTag = new Map();
  for (const page of state.pdfCoilPages || []) {
    if (page.manualFills && page.tag) priorFillsByTag.set(page.tag, page.manualFills);
  }
  state.pdfIntakeSummary = workflow.pdf_intake_summary;
  state.pdfCoilPages = workflow.pdf_coil_pages || [];
  state.activePdfCoilPageIndex = state.pdfCoilPages.length ? 0 : -1;
  state.reviewedCoils = new Set();  // fresh PDF -> nothing reviewed yet
  // Drop the previous submittal's comparison verdicts. They describe coils that are no
  // longer on screen, and a tag can repeat across projects (CDXC-1 is in every one), so
  // keeping them would paint this analyze's rows from the last one's numbers. Cleared
  // rather than left to be overwritten: the checklist re-fill is async and best-effort,
  // and it may never arrive (auto-fill off, or Excel unavailable).
  state.checklistBySlot = null;
  state.checklistRefillPending = false;
  state.ccsiVerdictsByTag = {};
  setSelectedQuotePdfFile(null);    // fresh analyze -> clear the prior quote PDF choice
  renderShell(workflowToUiState(state.ui, workflow, null));
  elements.savedStatus.textContent = statusText;
  refreshMechanicalFit();
  // Background, best-effort — never blocks analyze. With prior manual fills to re-apply,
  // the fill is deferred to reapplyManualFills so Excel runs ONCE, on the corrected
  // values, instead of once now on the pre-override ones and again after.
  if (priorFillsByTag.size) reapplyManualFills(priorFillsByTag);
  else maybeAutoFillChecklist();
}

// Headless re-apply of persisted manual fills after a full re-analyze. Each coil with
// prior fills is re-derived via /api/coil-drawing/derive (which runs BOTH the Tier-A
// engine re-run and Tier-B override), stored back onto its page WITHOUT rendering; the
// active coil is re-rendered ONCE at the end (finding MEDIUM-1 — no active-UI churn from
// background coils). Promise.allSettled isolates a single coil's failure (finding LOW-1).
async function reapplyManualFills(priorFillsByTag) {
  const jobs = [];
  for (const page of state.pdfCoilPages) {
    const fills = page.tag ? priorFillsByTag.get(page.tag) : null;
    const td = (page.workflow || {}).template_drawing;
    if (!fills || !td || td.error) continue;
    page.manualFills = fills;  // restore so a subsequent re-analyze keeps them
    jobs.push(
      deriveCoilDrawing(
        td, fills.productLine || td.product_type || "",
        fills.unitSize || td.unit_size || "", fills, { headless: true, page },
      ),
    );
  }
  if (!jobs.length) {
    maybeAutoFillChecklist();  // nothing to re-apply — the plain analyze-time fill
    return;
  }
  const results = await Promise.allSettled(jobs);
  const failed = results.filter((r) => r.status === "rejected").length;
  // Re-render the visible coil once from its (now re-derived) cached workflow.
  if (state.activePdfCoilPageIndex >= 0) selectPdfCoilPage(state.activePdfCoilPageIndex);
  // ONE checklist fill for the whole fan-out (the headless derives deliberately skip it),
  // now that every coil's fills are back on its page.
  scheduleChecklistRefill();
  if (elements.savedStatus) {
    const ok = jobs.length - failed;
    elements.savedStatus.textContent =
      `Re-applied ${ok} of ${jobs.length} manual fill${jobs.length === 1 ? "" : "s"}` +
      (failed ? ` (${failed} failed)` : "");
  }
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
//
// `previous` is the fit_inputs this REPLACES. The drain-pan option is read once from the
// whole submittal (it lives on a configuration page, not in any per-coil spec), so it is
// not present on `spec` and would be dropped on every manual correction — the INSTALL FIT
// would silently fall back to CANNOT_EVALUATE the moment the engineer fixed anything.
// Carry it forward instead of re-deriving it, which the browser could not do anyway.
function fitInputFromSpec(spec, previous) {
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
    drain_pan_option: previous?.drain_pan_option ?? null,
    drain_pan_option_reason: previous?.drain_pan_option_reason ?? "",
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
      // A note used to mean "this coil could not be evaluated at all", so it returned
      // early. The partner-size guard also sets a note, but its verdicts DO exist as
      // CANNOT_EVALUATE and carry the casing/CD numbers the engineer needs to work out
      // WHICH size is wrong — returning early there would hide the evidence for the very
      // warning being shown. So: early-return only when there is genuinely nothing else.
      if (c.note && !c.width && !c.height && !c.drain_pan) {
        return `<div class="fit-coil">${head}<p class="fit-note">⚠ ${escapeHtml(c.note)}</p></div>`;
      }
      const noteLine = c.note
        ? `<p class="fit-note">⚠ ${escapeHtml(c.note)}</p>`
        : "";
      const dp = c.drain_pan;
      const dpLine = dp
        ? `<div class="fit-line">${fitChip(dp.verdict)} <span>Drain pan</span> ${escapeHtml(dp.detail)}</div>`
        : "";
      return `
        <div class="fit-coil">
          ${head}
          ${noteLine}
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
  syncManualParamActions();
});

elements.manualParamApply?.addEventListener("click", () =>
  submitDrawingParamOverrides(state.lastTemplateDrawing),
);

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
    // Use the already-warmed map SYNCHRONOUSLY when present: a cold `await fetch` here would
    // run between the click and the clipboard write, expiring the write's transient user
    // activation so writeText silently rejects and leaves stale clipboard content (the
    // intermittent "Could not parse JSON" on the CCSI side). Cold path only on the very
    // first copy before the warm-up below resolves.
    const fieldMap = state.ccsiFieldMap || (await loadCcsiFieldMap());
    const payload = buildCcsiAutofillPayload(state.ui, fieldMap);
    const copied = await copyText(JSON.stringify(payload, null, 2));
    if (!copied) {
      elements.ccsiAutofillStatus.textContent =
        "Copy to clipboard was blocked — keep this CoilForge tab focused and click again, or use ▶ Send to CCSI (no clipboard).";
      return;
    }
    const fillable = payload.fields.filter((field) => field.value !== null).length;
    elements.ccsiAutofillStatus.textContent =
      `Copied CCSI payload — ${fillable}/${payload.fields.length} fields have a value to review (map v${payload.field_map_version}). Switch to the CCSI form and run the userscript.`;
  } catch (error) {
    elements.ccsiAutofillStatus.textContent = `Could not build payload: ${error.message}`;
  }
});

setupCcsiBookmarklet();
// Warm the CCSI field-map cache up front so "Copy CCSI autofill payload" can write the
// clipboard synchronously inside the click gesture (see the handler above).
loadCcsiFieldMap().catch(() => {});

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
    // Was state.lastProjectReview?.summary?.exceptions_K until the Project Review panel was
    // removed 2026-07-28. null is the same value the no-review-run path always produced, so
    // the email context is unchanged; pinned literal so this doesn't read as a live feature.
    exceptionsK: null,
    // Keep the revised PDF so "Finalize deliverable" can file + attach it without rebuilding.
    revisedBase64: pkg.pdf_base64 || null,
  };
  const finalizeBtn = document.querySelector("#finalize-deliverable");
  if (finalizeBtn) finalizeBtn.hidden = false;
  // File the deliverable in the SAME click (John 2026-08-30) — the three docs stop
  // living in Downloads. The Outlook draft is deliberately skipped: John chose
  // "file only" for the automatic step and keeps the draft on its own button.
  await fileDeliverable({ skipDraft: true });
}

// File the deliverable — MOVE the original quote + revised quote + auto-generated
// checklist out of Downloads into the project's DirectCoil folder, and (unless
// skipDraft) open a pre-filled Outlook DRAFT with the revised PDF attached.
// Server-side (SharePoint filing + Outlook COM); never sends.
//
// Called twice per deliverable by design: Build fires it with skipDraft, and the button
// re-runs it for the draft. The second run finds the same three byte-identical files
// already filed, which the backend treats as `already_filed`, not a conflict.
async function fileDeliverable({ skipDraft = false, overwrite = false } = {}) {
  const summary = document.querySelector("#deliverable-summary");
  const ctx = state.lastQuotePackage;
  if (!ctx || !ctx.revisedBase64) {
    if (summary) summary.textContent = "Build the quote package first.";
    return null;
  }
  const submittal = state.selectedPdfFile;
  const quote = state.selectedQuotePdfFile;
  if (!isPdfFile(submittal) || !isPdfFile(quote)) {
    if (summary) {
      summary.textContent =
        "Need both the analyzed submittal PDF and the quote PDF to file the deliverable.";
    }
    return null;
  }
  if (summary) {
    summary.textContent = skipDraft
      ? "Filing the deliverable into the project's DirectCoil folder…"
      : "Filing docs & drafting email…";
  }
  const [subBytes, quoteBytes] = await Promise.all([submittal.arrayBuffer(), quote.arrayBuffer()]);
  const body = {
    submittal_pdf_base64: arrayBufferToBase64(subBytes),
    submittal_filename: submittal.name,
    quote_pdf_base64: arrayBufferToBase64(quoteBytes),
    quote_filename: quote.name,
    revised_pdf_base64: ctx.revisedBase64,
    // Same manual fills the checklist panel was filled with, so the .xlsx filed with the
    // order is the override-bearing one (and reuses its cache entry — no second Excel run).
    checklist_overrides: collectChecklistOverrides(),
    skip_draft: skipDraft,
    overwrite,
  };
  let res;
  try {
    res = await requestJson("/api/deliverable/finalize", {
      method: "POST",
      body: JSON.stringify(body),
    });
  } catch (err) {
    if (summary) summary.textContent = `Filing failed: ${err.message || err}`;
    return null;
  }
  renderDeliverableResult(res, { skipDraft });
  return res;
}

// A conflict is not an error — nothing was written and John picks. Rendered with its own
// Overwrite/Cancel pair rather than a confirm(), so the file list stays readable.
function renderDeliverableResult(res, { skipDraft }) {
  const summary = document.querySelector("#deliverable-summary");
  if (!summary) return;
  if (res.status === "conflict") {
    const rows = (res.conflicts || [])
      .map(
        (c) =>
          `<span class="quote-package-warning">⚠ ${escapeHtml(c.name)} — already there with different content</span>`
      )
      .join("<br>");
    summary.innerHTML =
      `<strong>Nothing was filed.</strong> ${escapeHtml(res.folder)} already holds `
      + `${(res.conflicts || []).length} file(s) under the same name but with different content:`
      + `<br>${rows}<br>`
      + `<button id="deliverable-overwrite" type="button">Overwrite and file</button> `
      + `<button id="deliverable-cancel" class="secondary-action" type="button">Cancel</button>`;
    document.querySelector("#deliverable-overwrite")?.addEventListener("click", () => {
      fileDeliverable({ skipDraft, overwrite: true }).catch((error) => {
        summary.textContent = `Filing failed: ${error.message || error}`;
      });
    });
    document.querySelector("#deliverable-cancel")?.addEventListener("click", () => {
      summary.textContent = "Cancelled — nothing was filed.";
    });
    return;
  }
  const files = (res.files_written || [])
    .map((p) => `<span class="quote-package-coil">${escapeHtml(p)}</span>`)
    .join("<br>");
  // Only the non-"moved" ones matter: a file left behind in Downloads is the one thing
  // John would otherwise discover weeks later as a stale duplicate.
  const leftBehind = (res.downloads_cleanup || [])
    .filter((entry) => entry.status !== "moved")
    .map(
      (entry) =>
        `<span class="quote-package-warning">⚠ Downloads: ${escapeHtml(entry.name)} — ${escapeHtml(entry.status)}</span>`
    )
    .join("<br>");
  const draft = skipDraft
    ? ""
    : res.draft_opened
      ? `<br><span class="quote-package-coil">Outlook draft opened — review &amp; send: <strong>${escapeHtml(res.subject)}</strong></span>`
      : `<br><span class="quote-package-warning">⚠ Draft not opened: ${escapeHtml(res.draft_status || "unknown")}</span>`;
  const chk =
    res.checklist_status && res.checklist_status !== "ok"
      ? `<br><span class="quote-package-warning">⚠ Checklist: ${escapeHtml(res.checklist_status)}</span>`
      : "";
  summary.innerHTML =
    `<strong>Filed to</strong> ${escapeHtml(res.folder)}<br>${files}`
    + (leftBehind ? `<br>${leftBehind}` : "")
    + draft
    + chk;
}

document.querySelector("#finalize-deliverable")?.addEventListener("click", () => {
  fileDeliverable().catch((error) => {
    const summary = document.querySelector("#deliverable-summary");
    if (summary) summary.textContent = error.message;
  });
});

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
    { match: "✓", mismatch: "✗", missing_one: "·", both_missing: "—", overridden: "✎" }[
      verdict
    ] || ""
  );
}

// "was 0.875 (reason)" — what a manual override replaced. Shown as a hover title so the
// table stays scannable while never hiding that the value is human-supplied, not derived.
function _overrideTitle(override) {
  if (!override) return "";
  const was =
    override.previous_value === null || override.previous_value === undefined
      ? "blank"
      : override.previous_value;
  const reason = override.reason ? ` — ${override.reason}` : "";
  return `Manual override (${override.key}): was ${was}${reason}`;
}

function renderChecklistSheet(sheet) {
  const inputs = (sheet.inputs || [])
    .map((i) => {
      const blank = i.value === null || i.value === undefined || i.value === "";
      const cls = i.override ? "checklist-overridden" : blank ? "checklist-blank" : "";
      const badge = i.override
        ? ` <span class="checklist-override-badge" title="${escapeHtml(_overrideTitle(i.override))}">✎</span>`
        : "";
      return `<tr class="${cls}">
        <td>${escapeHtml(i.label)}${badge}</td>
        <td>${_checklistCell(i.value)}</td>
        <td class="checklist-src">${escapeHtml(i.note || i.source || "")}</td></tr>`;
    })
    .join("");
  const comps = (sheet.comparisons || [])
    .map(
      (c) => `<tr class="checklist-${c.verdict}"${
        c.override ? ` title="${escapeHtml(_overrideTitle(c.override))}"` : ""
      }>
        <td>${escapeHtml(c.label)}</td>
        <td>${_checklistCell(c.coilforge)}</td>
        <td>${_checklistCell(c.checklist)}</td>
        <td class="checklist-verdict">${_verdictIcon(c.verdict)}</td></tr>`
    )
    .join("");
  const overrides = sheet.override_count
    ? ` · ${sheet.override_count} overridden`
    : "";
  return `<div class="checklist-sheet">
    <h4>${escapeHtml(sheet.tag)}
      <span class="subtle-label">${escapeHtml(sheet.category)} · ${sheet.mismatch_count} mismatch${overrides}</span></h4>
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

// The engineer's per-coil manual fills, in the shape /api/checklist/fill consumes. Keyed
// by tag (the same identity reapplyManualFills uses) because the checklist re-derives its
// coils from the submittal and cannot rely on page order. Empty => the checklist keeps its
// original raw-PDF request, byte-for-byte.
function collectChecklistOverrides() {
  const out = [];
  for (const page of state.pdfCoilPages || []) {
    const fills = page.manualFills;
    if (!page.tag || !fills) continue;
    const engineInputs = fills.engineInputs || {};
    const paramOverrides = fills.paramOverrides || [];
    if (!Object.keys(engineInputs).length && !paramOverrides.length) continue;
    out.push({
      tag: page.tag,
      engine_inputs: engineInputs,
      param_overrides: paramOverrides,
      reason: fills.reason || null,
    });
  }
  return out;
}

// The coil whose rows the Drawing Parameters panel is currently showing. Everything
// per-coil (checklist verdicts, CCSI verdicts) is keyed on this, so nothing can bleed
// from one coil to the next.
function activeCoilTag() {
  const page = state.pdfCoilPages?.[state.activePdfCoilPageIndex];
  return page?.tag || null;
}

// Index the checklist review so the Drawing Parameters panel can show each dimension's
// disagreement inline — John reviews that panel constantly and was scrolling down to the
// comparison table to cross-check every number by eye.
//
// Rows deliberately dropped, because painting them would train him to ignore the colour:
//   * no slot            — the row has no engine dimension to join on (never happens today)
//   * coilforge === "N/A"— past the coil's circuit count; compare() reports the literal
//                          string, and "N/A" vs a number scores as a mismatch
//   * both_missing       — neither side has a value; nothing to disagree about
function ingestChecklistReview(review) {
  const byTag = new Map();
  for (const sheet of review?.sheets || []) {
    const bySlot = new Map();
    for (const row of sheet.comparisons || []) {
      if (!row.slot) continue;
      if (String(row.coilforge ?? "").trim().toUpperCase() === "N/A") continue;
      if (row.verdict === "both_missing") continue;
      bySlot.set(row.slot, row);
    }
    byTag.set(sheet.tag, bySlot);
  }
  state.checklistBySlot = byTag;
  state.checklistRefillPending = false;
  // Repaint the panel in place. The review arrives seconds after the panel first
  // rendered (Excel COM), and it carries EVERY sheet, so there is no "which coil was
  // active when it landed" race — the lookup is by the active tag at render time.
  if (state.ui) renderDrawingParameters(state.ui);
}

// How many coil pages the checklist could not be joined to. Surfaced next to the fill
// summary so "this row has no badge" is distinguishable from "this coil matched no sheet"
// (an untagged page falls back to "Coil 3" and joins nothing).
function checklistUnjoinedCount() {
  if (!state.checklistBySlot) return 0;
  return (state.pdfCoilPages || []).filter(
    (page) => !page.tag || !state.checklistBySlot.has(page.tag),
  ).length;
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
    const overrides = collectChecklistOverrides();
    // Two request forms on purpose: with no manual fills this is the ORIGINAL raw-PDF
    // POST (unchanged); the JSON form is used only when there is something to carry.
    const request = overrides.length
      ? {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-CoilForge-Filename": sanitizeHeaderValue(file.name),
            ...coverPageHeader(),
          },
          body: JSON.stringify({
            submittal_pdf_base64: arrayBufferToBase64(pdfBytes),
            coil_overrides: overrides,
          }),
        }
      : {
          method: "POST",
          headers: {
            "Content-Type": "application/pdf",
            "X-CoilForge-Filename": sanitizeHeaderValue(file.name),
            ...coverPageHeader(),
          },
          body: pdfBytes,
        };
    const review = await requestJson("/api/checklist/fill", request);
    ingestChecklistReview(review);
    renderChecklistReview(review);
    if (summary) {
      const applied = review.override_total
        ? ` · <strong>${review.override_total} manual override(s) applied</strong>`
        : "";
      const unjoined = checklistUnjoinedCount();
      const unmatched = unjoined
        ? ` · <strong>${unjoined} coil page(s) matched no sheet</strong> (no inline flags there)`
        : "";
      summary.innerHTML =
        `Saved <strong>${escapeHtml(review.saved_path || "")}</strong> · ` +
        `${review.mismatch_total} dimension mismatch(es) to review${applied}${unmatched} · ` +
        `review aid, not exported`;
    }
  } catch (error) {
    if (summary) summary.textContent = `Checklist fill failed: ${error.message || error}`;
  }
}

// Re-fill the checklist after a manual correction so the sheet (and the .xlsx that gets
// filed) states the values CoilForge is actually drawing. Debounced: one Apply click can
// change several fields, and each Excel COM run costs seconds. Honours the same auto
// toggle as the analyze-time fill, so switching it off silences this too.
let _checklistRefillTimer = null;

function scheduleChecklistRefill() {
  if (!checklistAutoEnabled()) return;
  // The panel's numbers have just changed while the indexed review still describes the
  // pre-correction values. Mark it explicitly rather than inferring staleness from a
  // value difference — see state.checklistRefillPending.
  state.checklistRefillPending = true;
  if (state.ui) renderDrawingParameters(state.ui);
  if (_checklistRefillTimer) clearTimeout(_checklistRefillTimer);
  _checklistRefillTimer = setTimeout(() => {
    _checklistRefillTimer = null;
    fillCoilChecklist();
  }, 1500);
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

// The offline CCSI-export audit (auditCcsiExport/renderCcsiAudit/renderCcsiAuditCoil) and
// the Project Review — exceptions-first gate (runProjectReview/acceptPassingCoils/
// renderProjectGate/renderGateCoil) lived here until 2026-07-28, when John removed both
// panels to keep the review flow to a minimum set of buttons. Their backends are KEPT and
// still tested: POST /api/ccsi/audit-export (ccsi/export_audit.py) and POST
// /api/review/project (review/project_gate.py, also re-derived by capture/record.py).
// The LIVE /api/ccsi-compare path is a different feature and is untouched.

// ---------------------------------------------------------------------------
// Supplier selector (Direct Coil default vs Ambient quick-ship). Persisted so the
// choice sticks across reloads. Direct Coil = today's behavior (byte-identical); the
// Ambient comparison panel is CSS-gated on body[data-supplier="ambient"].
// ---------------------------------------------------------------------------
const SUPPLIER_KEY = "coilforge.supplier";

function applySupplier(supplier) {
  state.supplier = supplier === "ambient" ? "ambient" : "direct_coil";
  document.body.dataset.supplier = state.supplier;
  document.querySelectorAll(".supplier-btn").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.supplier === state.supplier);
  });
  const title = document.querySelector("#page-title");
  if (title) {
    title.textContent = state.supplier === "ambient" ? "Ambient (Quick-Ship)" : "Direct Coil Draft";
  }
}

(function initSupplierSwitch() {
  const stored = localStorage.getItem(SUPPLIER_KEY);
  applySupplier(stored === "ambient" ? "ambient" : "direct_coil");
  document.querySelectorAll(".supplier-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      applySupplier(btn.dataset.supplier);
      localStorage.setItem(SUPPLIER_KEY, state.supplier);
    });
  });
})();

// Ambient Dynamics quote comparison — baseline submittal + Ambient Performance PDF ->
// per-coil green/red/grey compare with Coil Utilities acceptance bands. POSTs multipart
// to /api/ambient/compare (headers:{} so the browser sets the multipart boundary — a
// forced application/json would break form parsing). Review aid only; nothing exported.
async function runAmbientCompare() {
  const summary = document.querySelector("#ambient-summary");
  const results = document.querySelector("#ambient-results");
  if (!state.ambientBaselineFile || !state.ambientReturnFile) return;
  summary.textContent = "Comparing Ambient performance vs the baseline…";
  results.innerHTML = "";
  try {
    const form = new FormData();
    form.append("baseline", state.ambientBaselineFile);
    form.append("ambient", state.ambientReturnFile);
    const report = await requestJson("/api/ambient/compare", {
      method: "POST",
      body: form,
      headers: {},
    });
    renderAmbientCompare(report);
  } catch (error) {
    summary.textContent = `Ambient comparison failed: ${error.message || error}`;
  }
}

function renderAmbientCompare(report) {
  const summary = document.querySelector("#ambient-summary");
  const results = document.querySelector("#ambient-results");
  const coils = (report && report.coils) || [];
  if (!coils.length) {
    summary.textContent = "No coils to compare (check the two PDFs).";
    results.innerHTML = "";
    return;
  }
  const mismatchTotal = report.mismatch_total || 0;
  const notCompared = (report.not_compared || []).length;
  const warnings = (report.ambient_warnings || []).concat(report.warnings || []);
  let head =
    `${coils.length} coil(s) · <strong>${mismatchTotal}</strong> field(s) differ` +
    (notCompared ? ` · <strong>${notCompared}</strong> not compared` : "") +
    ` · review aid, not exported`;
  if (warnings.length) {
    head += `<div class="ambient-warns">${warnings.map((w) => `⚠ ${escapeHtml(w)}`).join("<br>")}</div>`;
  }
  summary.innerHTML = head;
  results.innerHTML = coils.map(renderAmbientCoil).join("");
}

function renderAmbientCoil(coil) {
  if (coil.not_compared_reason) {
    return (
      `<div class="ccsi-audit-coil ambient-coil"><h4>${escapeHtml(coil.tag || "Coil")} ` +
      `<span class="subtle-label">${escapeHtml(coil.category || "")}</span> ` +
      `<span class="ccsi-audit-badge has-mismatch">not compared</span></h4>` +
      `<p class="ambient-not-compared">${escapeHtml(coil.not_compared_reason)}</p></div>`
    );
  }
  const rows = (coil.rows || [])
    .map((r) => {
      const cls =
        r.verdict === "match"
          ? "dc-control--match"
          : r.verdict === "mismatch"
          ? "dc-control--mismatch"
          : "row-cannot";
      const fmt = (v) => (v === null || v === undefined ? "—" : v);
      const mark =
        r.verdict === "match"
          ? "✓"
          : r.verdict === "mismatch"
          ? "⚠ differ"
          : r.verdict === "cannot_evaluate"
          ? "— n/a"
          : r.verdict === "missing_one"
          ? "missing"
          : "";
      const note = r.note ? ` <span class="ambient-note">${escapeHtml(r.note)}</span>` : "";
      return (
        `<tr class="${cls}"><td>${escapeHtml(r.label)}</td>` +
        `<td>${escapeHtml(String(fmt(r.baseline)))}</td>` +
        `<td>${escapeHtml(String(fmt(r.ambient)))}</td>` +
        `<td>${escapeHtml(String(r.unit || ""))}</td>` +
        `<td>${mark}${note}</td></tr>`
      );
    })
    .join("");
  const mismatch = coil.mismatch_count || 0;
  const cannot = coil.cannot_evaluate_count || 0;
  const badge =
    mismatch > 0
      ? `<span class="ccsi-audit-badge has-mismatch">⚠ ${mismatch} differ</span>`
      : `<span class="ccsi-audit-badge">✓ all match</span>`;
  const cannotNote = cannot ? `<span class="ccsi-audit-note">${cannot} cannot evaluate</span>` : "";
  return (
    `<div class="ccsi-audit-coil ambient-coil"><h4>${escapeHtml(coil.tag || "Coil")} ` +
    `<span class="subtle-label">${escapeHtml(coil.category || "")}</span> ${badge} ${cannotNote}</h4>` +
    `<table class="ccsi-audit-table ambient-table"><thead><tr>` +
    `<th>Field</th><th>Baseline</th><th>Ambient</th><th>Unit</th><th></th>` +
    `</tr></thead><tbody>${rows}</tbody></table></div>`
  );
}

// Excel write-back (Compare mode): fill the comparison workbook's C (ours) + D (Ambient)
// columns from the two loaded PDFs and export a filled copy to Downloads. Enabled only when
// both PDFs are present. Review aid only; the template/OneDrive file is never touched.
function updateAmbientExcelBtn() {
  const btn = document.querySelector("#ambient-excel-fill");
  if (btn) btn.disabled = !(state.ambientBaselineFile && state.ambientReturnFile);
}

async function fillAmbientExcel() {
  const status = document.querySelector("#ambient-excel-status");
  if (!state.ambientBaselineFile || !state.ambientReturnFile) return;
  status.textContent = "Filling the comparison Excel…";
  try {
    const form = new FormData();
    form.append("baseline", state.ambientBaselineFile);
    form.append("ambient", state.ambientReturnFile);
    const report = await requestJson("/api/ambient/excel", { method: "POST", body: form, headers: {} });
    const sheets = (report.sheets || []).map((s) => s.tag).join(", ");
    const skipped = (report.skipped_labels || []).length;
    status.innerHTML =
      `✓ Saved to Downloads: <strong>${escapeHtml(report.saved_path || "")}</strong>` +
      ` · ${(report.sheets || []).length} sheet(s): ${escapeHtml(sheets)}` +
      (skipped ? ` · ${skipped} label(s) unmatched` : "") +
      ` · review aid, original template untouched`;
  } catch (error) {
    status.textContent = `Excel fill failed: ${error.message || error}`;
  }
}

document.querySelector("#ambient-excel-fill")?.addEventListener("click", fillAmbientExcel);

document.querySelector("#ambient-baseline-file")?.addEventListener("change", (event) => {
  const file = event.target.files?.[0] || null;
  state.ambientBaselineFile = file;
  const nameEl = document.querySelector("#ambient-baseline-name");
  if (nameEl) nameEl.textContent = file ? file.name : "No file selected";
  updateAmbientExcelBtn();
  runAmbientCompare();
});

document.querySelector("#ambient-return-file")?.addEventListener("change", (event) => {
  const file = event.target.files?.[0] || null;
  state.ambientReturnFile = file;
  const nameEl = document.querySelector("#ambient-return-name");
  if (nameEl) nameEl.textContent = file ? file.name : "No file selected";
  updateAmbientExcelBtn();
  runAmbientCompare();
});

// ---------------------------------------------------------------------------
// Ambient mode toggle (within the Ambient panel): "compare" (two files, today's flow)
// vs "package" (drop a submittal -> generate an Ambient performance page + drawing to
// hand to Ambient). Persisted; the data-ambient-mode flag is stamped before first paint
// (mirrors initSupplierSwitch) so the default compare flow never flashes/hides.
// ---------------------------------------------------------------------------
const AMBIENT_MODE_KEY = "coilforge.ambientMode";

function applyAmbientMode(mode) {
  state.ambientMode = mode === "package" ? "package" : "compare";
  document.body.dataset.ambientMode = state.ambientMode;
  document.querySelectorAll(".ambient-mode-btn").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.ambientMode === state.ambientMode);
  });
}

(function initAmbientMode() {
  const stored = localStorage.getItem(AMBIENT_MODE_KEY);
  applyAmbientMode(stored === "package" ? "package" : "compare");
  document.querySelectorAll(".ambient-mode-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      applyAmbientMode(btn.dataset.ambientMode);
      localStorage.setItem(AMBIENT_MODE_KEY, state.ambientMode);
    });
  });
})();

// Submittal -> Ambient package. POSTs multipart 'submittal' (+ optional 'ez_drawing') to
// /api/ambient/package (headers:{} so the browser sets the boundary). Review aid only.
async function runAmbientPackage() {
  const summary = document.querySelector("#ambient-package-summary");
  const results = document.querySelector("#ambient-package-results");
  if (!state.ambientSubmittalFile) return;
  summary.textContent = "Building the Ambient package from the submittal…";
  results.innerHTML = "";
  try {
    const form = new FormData();
    form.append("submittal", state.ambientSubmittalFile);
    if (state.ambientEzFile) form.append("ez_drawing", state.ambientEzFile);
    const report = await requestJson("/api/ambient/package", {
      method: "POST",
      body: form,
      headers: {},
    });
    renderAmbientPackage(report);
  } catch (error) {
    summary.textContent = `Ambient package failed: ${error.message || error}`;
    state.ambientPackageReady = false;
    updateAmbientQuoteRequestBtn();
  }
}

// Quote-request export (Package mode): the paper artifact John hands Ambient. Re-POSTs the
// SAME PDFs the package was built from — the server memoizes on those bytes, so this is a
// cache hit rather than a second parse, and the drawing SVGs never round-trip through the
// browser. Review aid only; every page is watermarked and export_allowed stays false.
function updateAmbientQuoteRequestBtn() {
  const btn = document.querySelector("#ambient-quote-request-pdf");
  if (btn) btn.disabled = !(state.ambientSubmittalFile && state.ambientPackageReady);
}

function ambientQuoteRequestExportName() {
  const source = state.ambientSubmittalFile?.name || "";
  const stem = source.replace(/\.pdf$/i, "").trim();
  return stem ? `${stem}_Ambient_Quote_Request.pdf` : "coilforge-ambient-quote-request.pdf";
}

async function exportAmbientQuoteRequestPdf() {
  const status = document.querySelector("#ambient-quote-request-status");
  if (!state.ambientSubmittalFile || !state.ambientPackageReady) return;
  status.textContent = "Building the quote request PDF…";
  const form = new FormData();
  form.append("submittal", state.ambientSubmittalFile);
  if (state.ambientEzFile) form.append("ez_drawing", state.ambientEzFile);
  const project = state.ui?.project || {};
  if (project.project_name) form.append("project_name", project.project_name);
  if (project.project_number) form.append("project_number", project.project_number);
  // headers:{} so the browser sets the multipart boundary (see runAmbientPackage above).
  const result = await requestJson("/api/ambient/quote-request-pdf", {
    method: "POST",
    body: form,
    headers: {},
  });
  downloadBase64Pdf(result.pdf_base64, ambientQuoteRequestExportName());
  const warnings = result.warnings || [];
  status.innerHTML =
    `✓ ${result.page_count} page(s) · ${result.coil_count} coil(s) · watermarked review aid, not an export` +
    (warnings.length
      ? `<div class="ambient-warns">${warnings.map((w) => `⚠ ${escapeHtml(w)}`).join("<br>")}</div>`
      : "");
}

document.querySelector("#ambient-quote-request-pdf")?.addEventListener("click", () => {
  exportAmbientQuoteRequestPdf().catch((error) => {
    const status = document.querySelector("#ambient-quote-request-status");
    if (status) status.textContent = `Export failed: ${error.message || error}`;
  });
});

function renderAmbientPackage(report) {
  const summary = document.querySelector("#ambient-package-summary");
  const results = document.querySelector("#ambient-package-results");
  const coils = (report && report.coils) || [];
  if (!coils.length) {
    summary.textContent = "No coils found in the submittal.";
    results.innerHTML = "";
    state.ambientPackageReady = false;
    updateAmbientQuoteRequestBtn();
    return;
  }
  state.ambientPackageReady = true;
  updateAmbientQuoteRequestBtn();
  const warnings = report.warnings || [];
  let head =
    `${coils.length} coil(s) · performance page + drawing to hand to Ambient` +
    ` · review aid, not exported`;
  if (warnings.length) {
    head += `<div class="ambient-warns">${warnings.map((w) => `⚠ ${escapeHtml(w)}`).join("<br>")}</div>`;
  }
  summary.innerHTML = head;
  results.innerHTML =
    `<p class="ambient-package-hand">Hand this to Ambient — every value is review-required; ` +
    `nothing here is calculated, approved, or exported.</p>` +
    coils.map(renderAmbientPackageCoil).join("");
}

function renderAmbientPackageCoil(coil) {
  const fmt = (v) => (v === null || v === undefined ? "—" : v);
  const lines = (coil.performance_lines || [])
    .map(
      (l) =>
        `<tr><td>${escapeHtml(l.label)}</td>` +
        `<td>${escapeHtml(String(fmt(l.value)))}</td>` +
        `<td>${escapeHtml(String(l.unit || ""))}</td>` +
        `<td>review</td></tr>`
    )
    .join("");
  const band = coil.acceptance_band
    ? `<p class="ambient-band">Acceptance band · ${escapeHtml(coil.acceptance_band.ekexva_kit || "")} ` +
      `(${escapeHtml(String(coil.acceptance_band.nominal_tons || ""))} tons) · capacity ` +
      `${escapeHtml(String((coil.acceptance_band.capacity_band_mbh || []).join(" – ")))} MBH` +
      (coil.acceptance_band.circuits_assumed ? ` · ⚠ circuits assumed = 1 (not stated)` : "") +
      `</p>`
    : "";
  const missing = (coil.missing_fields || []).length
    ? `<p class="ambient-missing">Missing (not guessed): ${escapeHtml(coil.missing_fields.join(", "))}</p>`
    : "";
  const drawing = coil.drawing || {};
  let drawingHtml;
  if (drawing.svg) {
    const tag = drawing.source === "ez_coil" ? "EZ Coil drawing" : "CoilForge drawing";
    drawingHtml =
      `<div class="ambient-drawing-preview" role="button" tabindex="0" ` +
      `aria-label="${escapeHtml(tag)} — click to enlarge">${drawing.svg}</div>` +
      `<p class="ambient-drawing-hint">🔍 Click the drawing to enlarge</p>`;
  } else if (drawing.source === "ez_coil") {
    drawingHtml = `<p class="ambient-drawing-omitted">EZ Coil drawing supplied — attached separately.</p>`;
  } else {
    drawingHtml = `<p class="ambient-drawing-omitted">Drawing omitted: ${escapeHtml(drawing.omitted_reason || "not generated")}</p>`;
  }
  return (
    `<div class="ccsi-audit-coil ambient-coil"><h4>${escapeHtml(coil.tag || "Coil")} ` +
    `<span class="subtle-label">${escapeHtml(coil.category || "")}</span></h4>` +
    band +
    `<table class="ccsi-audit-table ambient-table"><thead><tr>` +
    `<th>Field</th><th>Value</th><th>Unit</th><th></th>` +
    `</tr></thead><tbody>${lines}</tbody></table>` +
    missing +
    drawingHtml +
    `</div>`
  );
}

document.querySelector("#ambient-submittal-file")?.addEventListener("change", (event) => {
  const file = event.target.files?.[0] || null;
  state.ambientSubmittalFile = file;
  const nameEl = document.querySelector("#ambient-submittal-name");
  if (nameEl) nameEl.textContent = file ? file.name : "No file selected";
  // A new submittal invalidates the previous package until this run re-renders.
  state.ambientPackageReady = false;
  updateAmbientQuoteRequestBtn();
  runAmbientPackage();
});

document.querySelector("#ambient-ez-file")?.addEventListener("change", (event) => {
  const file = event.target.files?.[0] || null;
  state.ambientEzFile = file;
  const nameEl = document.querySelector("#ambient-ez-name");
  if (nameEl) nameEl.textContent = file ? file.name : "No file selected";
  if (state.ambientSubmittalFile) runAmbientPackage();
});

// Click-to-enlarge for the package drawings: clone the clicked SVG into a full-screen
// overlay (white paper, up to 92vw); click anywhere or press Esc to close. The overlay is
// created lazily and reused. Delegated so it works for every re-rendered coil card.
function openAmbientDrawingModal(svgEl) {
  let modal = document.querySelector("#ambient-drawing-modal");
  if (!modal) {
    modal = document.createElement("div");
    modal.id = "ambient-drawing-modal";
    modal.className = "ambient-drawing-modal";
    modal.innerHTML = `<div class="ambient-drawing-modal-inner"></div>`;
    modal.addEventListener("click", () => modal.classList.remove("open"));
    document.body.appendChild(modal);
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape") modal.classList.remove("open");
    });
  }
  const inner = modal.querySelector(".ambient-drawing-modal-inner");
  inner.innerHTML = "";
  inner.appendChild(svgEl.cloneNode(true));
  modal.classList.add("open");
}

document.querySelector("#ambient-package-results")?.addEventListener("click", (event) => {
  const preview = event.target.closest(".ambient-drawing-preview");
  if (!preview) return;
  const svg = preview.querySelector("svg");
  if (svg) openAmbientDrawingModal(svg);
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
