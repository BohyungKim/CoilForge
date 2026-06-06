const state = {
  ui: null,
  activeTab: "checklist",
};

const elements = {
  breadcrumb: document.querySelector("#breadcrumb"),
  savedStatus: document.querySelector("#saved-status"),
  draftId: document.querySelector("#draft-id"),
  groups: document.querySelector("#direct-coil-groups"),
  importSummary: document.querySelector("#import-summary"),
  sourceEvidence: document.querySelector("#source-evidence"),
  drawingPreview: document.querySelector("#drawing-preview"),
  drawingParameters: document.querySelector("#drawing-parameters"),
  performanceSummary: document.querySelector("#performance-summary"),
  validationSummary: document.querySelector("#validation-summary"),
  candidateStatus: document.querySelector("#candidate-status"),
  previewStatus: document.querySelector("#preview-status"),
  counts: {
    ready: document.querySelector("#count-ready"),
    review: document.querySelector("#count-review"),
    blocked: document.querySelector("#count-blocked"),
    unmapped: document.querySelector("#count-unmapped"),
  },
};

async function requestJson(url, options = {}) {
  const response = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(JSON.stringify(payload, null, 2));
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

  elements.breadcrumb.textContent = project.breadcrumb.join(" / ");
  elements.savedStatus.textContent = project.saved_status;
  elements.draftId.textContent = uiState.direct_coil_draft.draft_id;
  elements.counts.ready.textContent = counts.ready;
  elements.counts.review.textContent = counts.review_required;
  elements.counts.blocked.textContent = counts.blocked;
  elements.counts.unmapped.textContent = counts.unmapped;

  renderDirectCoilGroups(uiState);
  renderImportSummary(uiState);
  renderDrawingPreview(uiState);
  renderDrawingParameters(uiState);
  renderPerformance(uiState);
  renderValidation(uiState);
  updateTabVisibility();
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
  elements.candidateStatus.textContent = summary.selected_candidate.review_status;
  elements.importSummary.innerHTML = `
    <div><span>Project</span><strong>${uiState.project.project_name}</strong></div>
    <div><span>Coil tag</span><strong>${uiState.project.coil_tag}</strong></div>
    <div><span>Candidates</span><strong>${summary.candidate_count}</strong></div>
    <div><span>Raw data</span><strong>${summary.raw_private_data_included ? "present" : "excluded"}</strong></div>
  `;

  elements.sourceEvidence.innerHTML = "";
  uiState.source_evidence.fields.slice(0, 8).forEach((item) => {
    const row = document.createElement("div");
    row.className = "evidence-row";
    row.innerHTML = `<span>${item.label}</span><code>${item.evidence_ids.join(", ")}</code>`;
    elements.sourceEvidence.append(row);
  });
}

function renderDrawingPreview(uiState) {
  const preview = uiState.drawing_preview;
  elements.previewStatus.textContent = preview.preview_allowed ? "Preview ready" : "Blocked";
  elements.previewStatus.className = `status-chip ${preview.preview_allowed ? "status-review-required" : "status-blocked"}`;
  if (preview.svg) {
    elements.drawingPreview.innerHTML = preview.svg;
  } else {
    elements.drawingPreview.textContent = "Drawing preview blocked until required parameters are supplied.";
  }
}

function renderDrawingParameters(uiState) {
  elements.drawingParameters.innerHTML = "";
  Object.values(uiState.drawing_parameters.parameters).forEach((parameter) => {
    const item = document.createElement("div");
    item.className = `parameter-item ${statusClass(parameter.status)}`;
    item.innerHTML = `
      <span>${parameter.key}</span>
      <strong>${parameter.value ?? "Missing"}</strong>
      <em>${parameter.mode}</em>
    `;
    elements.drawingParameters.append(item);
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
    <div><span>Export</span><strong>${validation.export_status}</strong></div>
    <div><span>Blocked fields</span><strong>${validation.blocked_fields.length}</strong></div>
  `;
}

function updateTabVisibility() {
  document.querySelectorAll("[data-tab]").forEach((button) => {
    button.classList.toggle("active", button.dataset.tab === state.activeTab);
  });
  document.querySelectorAll(".draft-field").forEach((row) => {
    const group = row.dataset.group;
    const show =
      state.activeTab === "checklist" ||
      (state.activeTab === "performance" && group.includes("Airside")) ||
      (state.activeTab === "performance" && group.includes("Refrigerant")) ||
      (state.activeTab === "drawing" && group.includes("Drawing")) ||
      state.activeTab === "review";
    row.hidden = !show;
  });
}

async function loadUiState() {
  const uiState = await requestJson("/api/ui/default");
  renderShell(uiState);
}

async function runWorkflow() {
  const demo = await requestJson("/api/workflow/default-demo");
  const uiWorkflow = await requestJson("/api/workflow/submittal-to-drawing", {
    method: "POST",
    body: JSON.stringify(demo.input),
  });
  state.ui.validation = {
    ...state.ui.validation,
    ...uiWorkflow.validation,
    blocked_fields: state.ui.readiness_report.blocked_fields.map((field) => field.field_key),
  };
  state.ui.drawing_preview = {
    svg: uiWorkflow.svg,
    metadata: uiWorkflow.metadata,
    preview_allowed: uiWorkflow.validation.preview_allowed,
    export_allowed: uiWorkflow.validation.export_allowed,
  };
  renderShell(state.ui);
}

document.querySelectorAll("[data-tab]").forEach((button) => {
  button.addEventListener("click", () => {
    state.activeTab = button.dataset.tab;
    updateTabVisibility();
  });
});

document.querySelector("#analyze").addEventListener("click", () => {
  runWorkflow().catch((error) => {
    elements.validationSummary.textContent = error.message;
  });
});

document.querySelector("#apply-draft").addEventListener("click", () => {
  elements.savedStatus.textContent = "Direct Coil draft refreshed from sanitized workflow";
});

document.querySelector("#update-drawing").addEventListener("click", () => {
  runWorkflow().catch((error) => {
    elements.validationSummary.textContent = error.message;
  });
});

document.querySelector("#save-draft").addEventListener("click", () => {
  elements.savedStatus.textContent = "Save Draft is a placeholder in Phase 2B.11";
});

document.querySelector("#calculate-button").addEventListener("click", () => {
  elements.savedStatus.textContent = "Calculate is not implemented in this review shell";
});

loadUiState().catch((error) => {
  document.body.innerHTML = `<main class="load-error"><pre>${error.message}</pre></main>`;
});
