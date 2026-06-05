const editableFields = [
  "coil_name",
  "model_number",
  "source_case_id",
  "coil_category",
  "header_type",
  "rows",
  "fin_height",
  "fin_length",
  "fin_density_fpi",
  "casing_height",
  "casing_length",
  "casing_depth",
  "top_flange",
  "bottom_flange",
  "return_bend_allowance",
  "coil_hand",
  "airflow_direction",
  "return_connection_size",
  "circuiting_display",
  "release_status",
  "drawing_status",
  "notes",
];

const numericFields = new Set([
  "rows",
  "fin_height",
  "fin_length",
  "fin_density_fpi",
  "casing_height",
  "casing_length",
  "casing_depth",
  "top_flange",
  "bottom_flange",
  "return_bend_allowance",
  "return_connection_size",
]);

const fieldLabels = {
  coil_name: "Coil name",
  model_number: "Model number",
  source_case_id: "Source case id",
  coil_category: "Coil category",
  header_type: "Header type",
  rows: "Rows",
  fin_height: "Fin height",
  fin_length: "Fin length",
  fin_density_fpi: "Fin density (FPI)",
  casing_height: "Casing height",
  casing_length: "Casing length",
  casing_depth: "Casing depth",
  top_flange: "Top flange",
  bottom_flange: "Bottom flange",
  return_bend_allowance: "Return bend allowance",
  coil_hand: "Coil hand",
  airflow_direction: "Airflow direction",
  return_connection_size: "Return connection size",
  circuiting_display: "Circuiting display",
  release_status: "Release status",
  drawing_status: "Drawing status",
  notes: "Notes",
};

const form = document.querySelector("#parameter-form");
const validationOutput = document.querySelector("#validation-output");
const snapshotOutput = document.querySelector("#snapshot-output");
const svgPreview = document.querySelector("#svg-preview");

let currentState = {};
let latestValidationReport = null;
let latestRendererMetadata = null;

function formatJson(value) {
  return JSON.stringify(value, null, 2);
}

function parseValue(field, value) {
  if (field === "notes") {
    return value
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean);
  }
  if (numericFields.has(field)) {
    const parsed = Number(value);
    return Number.isNaN(parsed) ? value : parsed;
  }
  return value;
}

function renderForm(state) {
  form.innerHTML = "";

  editableFields.forEach((field) => {
    const row = document.createElement("div");
    row.className = "field-row";

    const label = document.createElement("label");
    label.htmlFor = `field-${field}`;
    label.textContent = fieldLabels[field] || field;

    const value = state[field];
    const input =
      field === "notes" ? document.createElement("textarea") : document.createElement("input");
    input.id = `field-${field}`;
    input.name = field;
    input.value = Array.isArray(value) ? value.join("\n") : value ?? "";
    input.type = numericFields.has(field) ? "number" : "text";
    if (numericFields.has(field)) {
      input.step = field === "rows" ? "1" : "0.01";
    }
    input.addEventListener("input", () => {
      currentState[field] = parseValue(field, input.value);
      latestValidationReport = null;
      latestRendererMetadata = null;
      validationOutput.textContent = "Current values changed. Run validation before snapshot review.";
    });

    row.append(label, input);
    form.append(row);
  });
}

function renderValidationReport(report) {
  validationOutput.innerHTML = "";

  const summary = document.createElement("div");
  summary.className = `validation-summary status-${report.validation_status}`;
  summary.textContent = `Status: ${report.validation_status} | pass ${report.summary.pass_count} | warn ${report.summary.warn_count} | fail ${report.summary.fail_count} | blocked ${report.summary.blocked_count} | n/a ${report.summary.not_applicable_count}`;
  validationOutput.append(summary);

  const checks = document.createElement("div");
  checks.className = "validation-checks";
  report.checks.forEach((check) => {
    const row = document.createElement("div");
    row.className = `validation-check check-${check.status}`;
    const status = document.createElement("span");
    status.className = "check-status";
    status.textContent = check.status;
    const body = document.createElement("span");
    body.textContent = `${check.check_id}: ${check.message}`;
    row.append(status, body);
    checks.append(row);
  });
  validationOutput.append(checks);
}

async function requestJson(url, options = {}) {
  const response = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(formatJson(payload));
  }
  return payload;
}

async function loadDefaultState() {
  const payload = await requestJson("/api/default-state");
  currentState = payload.state;
  latestValidationReport = null;
  latestRendererMetadata = null;
  renderForm(currentState);
  validationOutput.textContent = "Default state loaded. Validation has not run.";
  snapshotOutput.textContent = formatJson({ fixture: payload.fixture });
  svgPreview.textContent = "SVG preview has not run.";
}

async function runValidation() {
  latestValidationReport = await requestJson("/api/validate", {
    method: "POST",
    body: JSON.stringify(currentState),
  });
  renderValidationReport(latestValidationReport);
  return latestValidationReport;
}

async function renderSvg() {
  const validationReport = latestValidationReport || (await runValidation());
  const payload = await requestJson("/api/render-svg", {
    method: "POST",
    body: JSON.stringify({
      state: currentState,
      validation_report: validationReport,
      render_options: {
        viewBox: "0 0 1600 1200",
        include_review_watermark: true,
        include_markup_layer: true,
      },
    }),
  });
  latestRendererMetadata = payload.metadata;
  svgPreview.innerHTML = payload.svg;
  if (payload.warnings?.length || payload.blocked_fields?.length) {
    snapshotOutput.textContent = formatJson({
      renderer_metadata: payload.metadata,
      warnings: payload.warnings,
      blocked_fields: payload.blocked_fields,
    });
  }
  return payload;
}

async function generateSnapshot() {
  const validationReport = latestValidationReport || (await runValidation());
  const rendererMetadata = latestRendererMetadata || {};
  const payload = await requestJson("/api/generate-snapshot", {
    method: "POST",
    body: JSON.stringify({
      state: currentState,
      validation_report: validationReport,
      renderer_metadata: rendererMetadata,
    }),
  });
  snapshotOutput.textContent = formatJson(payload);
}

function showError(target, error) {
  target.textContent = error instanceof Error ? error.message : String(error);
}

document.querySelector("#load-default").addEventListener("click", () => {
  loadDefaultState().catch((error) => showError(snapshotOutput, error));
});

document.querySelector("#run-validation").addEventListener("click", () => {
  runValidation().catch((error) => showError(validationOutput, error));
});

document.querySelector("#render-svg").addEventListener("click", () => {
  renderSvg().catch((error) => showError(validationOutput, error));
});

document.querySelector("#generate-snapshot").addEventListener("click", () => {
  generateSnapshot().catch((error) => showError(snapshotOutput, error));
});

loadDefaultState().catch((error) => showError(snapshotOutput, error));
