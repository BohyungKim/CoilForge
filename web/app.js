const state = {
  ui: null,
  defaultInput: null,
  activeTab: "checklist",
  manualDrawingMode: false,
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
  blockedFields: document.querySelector("#blocked-fields"),
  candidateStatus: document.querySelector("#candidate-status"),
  previewStatus: document.querySelector("#preview-status"),
  coilName: document.querySelector("#edit-coil-name"),
  finnedHeight: document.querySelector("#edit-finned-height"),
  finnedLength: document.querySelector("#edit-finned-length"),
  airflowDirection: document.querySelector("#edit-airflow-direction"),
  manualDrawingMode: document.querySelector("#manual-drawing-mode"),
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

  renderDriverEditor(uiState);
  renderDirectCoilGroups(uiState);
  renderImportSummary(uiState);
  renderDrawingPreview(uiState);
  renderDrawingParameters(uiState);
  renderPerformance(uiState);
  renderValidation(uiState);
  renderBlockedFields(uiState);
  updateTabVisibility();
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
    const item = document.createElement("label");
    item.className = `parameter-item ${statusClass(parameter.status)}`;
    item.innerHTML = `
      <span>${parameter.key}</span>
      <input
        data-drawing-param="${parameter.key}"
        data-unit="${parameter.unit || "in"}"
        type="number"
        step="0.01"
        value="${parameter.value ?? ""}"
        ${state.manualDrawingMode ? "" : "disabled"}
      />
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

function workflowToUiState(previousUiState, workflow, workflowInput) {
  const readiness = workflow.readiness_report;
  const draft = workflow.direct_coil_input_draft;
  const coilName = workflow.drawing_intent.coil_name;
  return {
    ...previousUiState,
    project: {
      ...previousUiState.project,
      coil_tag: workflow.selected_candidate_summary.tag,
      saved_status: "Workflow analyzed from sanitized demo",
    },
    import_summary: {
      ...previousUiState.import_summary,
      candidate_count: workflow.candidates.length,
      selected_candidate: workflow.selected_candidate_summary,
      raw_private_data_included: false,
    },
    direct_coil_draft: {
      draft_id: draft.draft_id,
      source_canonical_record_id: draft.source_canonical_record_id,
      groups: draft.groups,
      fields: draft.fields,
      summary: draft.summary,
      export_status: draft.export_status,
    },
    readiness_report: readiness,
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
    actions: {
      ...previousUiState.actions,
      export_pdf: { enabled: false, placeholder: true },
    },
    workflow_payload_summary: {
      coil_name: coilName,
      finned_height: draft.fields.finned_height.value,
      finned_length: draft.fields.finned_length.value,
      airflow_direction: draft.fields.airflow_direction.value,
      preview_default_count: workflowInput.preview_defaults.length,
    },
  };
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
  const [uiState, demo] = await Promise.all([
    requestJson("/api/ui/default"),
    requestJson("/api/workflow/default-demo"),
  ]);
  state.defaultInput = structuredClone(demo.input);
  state.manualDrawingMode = false;
  renderShell(uiState);
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
    state.activeTab = button.dataset.tab;
    updateTabVisibility();
  });
});

elements.manualDrawingMode.addEventListener("change", () => {
  state.manualDrawingMode = elements.manualDrawingMode.checked;
  renderDrawingParameters(state.ui);
});

document.querySelector("#analyze").addEventListener("click", () => {
  runWorkflowFromCurrentState().catch((error) => {
    elements.validationSummary.textContent = error.message;
  });
});

document.querySelector("#apply-draft").addEventListener("click", () => {
  elements.savedStatus.textContent = "Direct Coil draft refreshed from sanitized workflow";
});

document.querySelector("#update-drawing").addEventListener("click", () => {
  runWorkflowFromCurrentState().catch((error) => {
    elements.validationSummary.textContent = error.message;
  });
});

document.querySelector("#save-draft").addEventListener("click", () => {
  elements.savedStatus.textContent = "Save Draft is a Phase 2B review shell placeholder";
});

document.querySelector("#calculate-button").addEventListener("click", () => {
  elements.savedStatus.textContent = "Calculate is not implemented in this review shell";
});

loadDefaultDemoWorkflow().catch((error) => {
  document.body.innerHTML = `<main class="load-error"><pre>${error.message}</pre></main>`;
});
