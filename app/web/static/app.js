const form = document.querySelector("#claimForm");
const photoInput = document.querySelector("#photoFiles");
const documentInput = document.querySelector("#documentFiles");
const analyzeButton = document.querySelector("#analyzeButton");
const advancedFields = document.querySelector("#advancedFields");
const photoQueueElement = document.querySelector("#photoQueue");
const documentQueueElement = document.querySelector("#documentQueue");
const evidenceValidation = document.querySelector("#evidenceValidation");
const queuedPhotos = [];
const queuedDocuments = [];

const views = {
  empty: document.querySelector("#emptyState"),
  loading: document.querySelector("#loadingState"),
  result: document.querySelector("#resultContent"),
  error: document.querySelector("#errorState"),
};

const numberFields = new Set([
  "claim_amount", "vehicle_value", "repair_estimate_amount", "driver_age",
  "vehicle_age_years", "vehicle_mileage", "number_of_previous_claims",
  "number_of_previous_rejected_claims", "accident_time_hour",
  "garage_previous_suspicious_claims",
]);

function showView(name) {
  Object.entries(views).forEach(([key, element]) => {
    element.hidden = key !== name;
  });
}

function renderPhotoQueue() {
  photoQueueElement.hidden = queuedPhotos.length === 0;
  photoQueueElement.innerHTML = queuedPhotos.map((file, index) => `
    <div class="queued-document">
      <div>
        <strong>${escapeHtml(file.name)}</strong>
        <span>Damage image</span>
      </div>
      <button type="button" data-photo-index="${index}">Remove</button>
    </div>
  `).join("");
  document.querySelector("#photoSummary").textContent = queuedPhotos.length
    ? `${queuedPhotos.length} ${queuedPhotos.length === 1 ? "image" : "images"} added`
    : "No photos selected";
}

function documentTypeLabel(type) {
  const option = document.querySelector(`#documentType option[value="${type}"]`);
  return option ? option.textContent : type.replaceAll("_", " ");
}

function inferredDocumentType(filename, fallback) {
  const normalized = filename.toLowerCase().replaceAll(/[_-]+/g, " ");
  const patterns = [
    ["POLICE_REPORT", ["police report", "police", "polizeibericht", "polizei"]],
    ["REPAIR_INVOICE", ["repair invoice", "invoice", "rechnung"]],
    ["ACCIDENT_REPORT", ["accident report", "unfallbericht"]],
    ["CLAIM_FORM", ["claim form", "claim"]],
    ["DRIVER_LICENSE", ["driver license", "driving license", "führerschein"]],
    ["VEHICLE_REGISTRATION", ["vehicle registration", "registration", "fahrzeugschein"]],
    ["WITNESS_STATEMENT", ["witness statement", "witness", "zeuge"]],
  ];
  const match = patterns.find(([, terms]) =>
    terms.some((term) => normalized.includes(term)));
  return match ? match[0] : fallback;
}

function documentTypeOptions(selectedType) {
  return [...document.querySelector("#documentType").options].map((option) => `
    <option value="${option.value}" ${option.value === selectedType ? "selected" : ""}>
      ${escapeHtml(option.textContent)}
    </option>
  `).join("");
}

function renderDocumentQueue() {
  documentQueueElement.hidden = queuedDocuments.length === 0;
  documentQueueElement.innerHTML = queuedDocuments.map((item, index) => `
    <div class="queued-document">
      <div>
        <strong>${escapeHtml(item.file.name)}</strong>
        <label class="queued-type-label">
          Classification
          <select class="queued-type" data-document-type-index="${index}">
            ${documentTypeOptions(item.type)}
          </select>
        </label>
      </div>
      <button type="button" data-document-index="${index}">Remove</button>
    </div>
  `).join("");
  document.querySelector("#documentSummary").textContent = queuedDocuments.length
    ? `${queuedDocuments.length} ${queuedDocuments.length === 1 ? "document" : "documents"} added`
    : "No documents added";
}

documentInput.addEventListener("change", () => {
  const selectedType = document.querySelector("#documentType").value;
  [...documentInput.files].forEach((file) => queuedDocuments.push({
    file,
    type: inferredDocumentType(file.name, selectedType),
  }));
  documentInput.value = "";
  evidenceValidation.hidden = true;
  renderDocumentQueue();
});

documentQueueElement.addEventListener("change", (event) => {
  const select = event.target.closest("[data-document-type-index]");
  if (!select) return;
  queuedDocuments[Number(select.dataset.documentTypeIndex)].type = select.value;
});

documentQueueElement.addEventListener("click", (event) => {
  const button = event.target.closest("[data-document-index]");
  if (!button) return;
  queuedDocuments.splice(Number(button.dataset.documentIndex), 1);
  renderDocumentQueue();
});

photoInput.addEventListener("change", () => {
  [...photoInput.files].forEach((file) => queuedPhotos.push(file));
  photoInput.value = "";
  evidenceValidation.hidden = true;
  renderPhotoQueue();
});

photoQueueElement.addEventListener("click", (event) => {
  const button = event.target.closest("[data-photo-index]");
  if (!button) return;
  queuedPhotos.splice(Number(button.dataset.photoIndex), 1);
  renderPhotoQueue();
});

document.querySelector("#toggleAdvanced").addEventListener("click", (event) => {
  advancedFields.hidden = !advancedFields.hidden;
  event.currentTarget.textContent = advancedFields.hidden
    ? "View additional details"
    : "Hide additional details";
});

document.querySelector("#resetButton").addEventListener("click", () => {
  form.reset();
  photoInput.value = "";
  documentInput.value = "";
  queuedPhotos.length = 0;
  queuedDocuments.length = 0;
  renderPhotoQueue();
  renderDocumentQueue();
  evidenceValidation.hidden = true;
  showView("empty");
  window.scrollTo({ top: 0, behavior: "smooth" });
});

document.querySelector("#retryButton").addEventListener("click", () => showView("empty"));

async function checkHealth() {
  const label = document.querySelector("#systemStatus");
  const dot = document.querySelector(".status-dot");
  try {
    const response = await fetch("/health");
    if (!response.ok) throw new Error();
    label.textContent = "API online";
    dot.classList.add("online");
  } catch {
    label.textContent = "API unavailable";
    dot.classList.remove("online");
  }
}

function claimPayload() {
  const data = new FormData(form);
  const claim = {};
  for (const [key, value] of data.entries()) {
    claim[key] = numberFields.has(key) ? Number(value) : value;
  }

  const hasPhotos = queuedPhotos.length > 0;
  const documentTypes = new Set(queuedDocuments.map((item) => item.type));
  Object.assign(claim, {
    recent_policy_change: form.elements.recent_policy_change.checked,
    has_police_report: documentTypes.has("POLICE_REPORT"),
    has_damage_photos: hasPhotos,
    has_repair_invoice: documentTypes.has("REPAIR_INVOICE"),
    has_witness_statement: documentTypes.has("WITNESS_STATEMENT"),
    third_party_involved: form.elements.third_party_involved.checked,
    photo_capture_date: hasPhotos ? claim.accident_date : null,
    invoice_date: claim.invoice_date || null,
    bank_account_hash: null,
    phone_hash: null,
    email_hash: null,
  });
  return claim;
}

async function api(url, options = {}) {
  const response = await fetch(url, options);
  if (!response.ok) {
    let message = `${response.status} ${response.statusText}`;
    try {
      const body = await response.json();
      message = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {}
    throw new Error(message);
  }
  return response.json();
}

async function uploadFiles(claimId, type, files) {
  if (!files.length) return [];
  const payload = new FormData();
  payload.append("document_type", type);
  [...files].forEach((file) => payload.append("files", file));
  return api(`/api/v1/claims/${encodeURIComponent(claimId)}/files/upload`, {
    method: "POST",
    body: payload,
  });
}

async function uploadQueuedDocuments(claimId) {
  const byType = new Map();
  queuedDocuments.forEach(({ file, type }) => {
    if (!byType.has(type)) byType.set(type, []);
    byType.get(type).push(file);
  });
  const uploads = await Promise.all(
    [...byType.entries()].map(([type, files]) => uploadFiles(claimId, type, files)),
  );
  return uploads.flat();
}

function setProgress(percent, title, detail) {
  document.querySelector("#progressBar").style.width = `${percent}%`;
  document.querySelector("#loadingTitle").textContent = title;
  document.querySelector("#loadingDetail").textContent = detail;
}

function riskClass(level) {
  return level.toLowerCase().replace("_", "-");
}

function renderResult(result, analyses) {
  document.querySelector("#resultClaimId").textContent = result.claim_id;
  document.querySelector("#fraudScore").textContent = result.fraud_score.toFixed(1);
  document.querySelector("#scoreRing").style.setProperty("--score", result.fraud_score);
  document.querySelector("#recommendedAction").textContent = result.recommended_action;
  document.querySelector("#confidenceLabel").textContent =
    `${result.confidence_score.toFixed(0)}% assessment confidence`;

  const pill = document.querySelector("#riskPill");
  pill.textContent = result.risk_level.replace("_", " ");
  pill.className = `risk-pill ${riskClass(result.risk_level)}`;

  document.querySelector("#structuredScore").textContent = result.structured_claim_score.toFixed(0);
  document.querySelector("#documentScore").textContent = result.document_score.toFixed(0);
  document.querySelector("#imageScore").textContent = result.image_score.toFixed(0);
  document.querySelector("#networkScore").textContent = result.network_score.toFixed(0);
  document.querySelector("#ruleScore").textContent = result.rule_based_score.toFixed(1);
  document.querySelector("#mlScore").textContent = result.ml_probability_score == null
    ? "Not available"
    : result.ml_probability_score.toFixed(1);

  const reasons = result.reasons || [];
  const warnings = result.warnings || [];
  document.querySelector("#reasonCount").textContent =
    `${reasons.length} ${reasons.length === 1 ? "finding" : "findings"}`
    + (warnings.length
      ? ` · ${warnings.length} ${warnings.length === 1 ? "notice" : "notices"}`
      : "");
  const reasonMarkup = reasons.length
    ? reasons.slice(0, 8).map((item) => `
      <article class="reason-item ${riskClass(item.severity)}">
        <strong>${escapeHtml(item.code.replaceAll("_", " "))}</strong>
        <p>${escapeHtml(item.message)}</p>
      </article>`).join("")
    : `<article class="reason-item low"><strong>No material risk indicators identified</strong>
       <p>The submitted information did not produce an escalation indicator.</p></article>`;
  const warningMarkup = warnings.map((message) => `
    <article class="reason-item medium">
      <strong>Assessment notice</strong>
      <p>${escapeHtml(message)}</p>
    </article>`).join("");
  document.querySelector("#reasonList").innerHTML = reasonMarkup + warningMarkup;

  document.querySelector("#fileCount").textContent =
    `${analyses.length} ${analyses.length === 1 ? "file" : "files"}`;
  document.querySelector("#fileList").innerHTML = analyses.length
    ? analyses.map((item) => {
      const encoder = item.analysis?.llm_encoder || {};
      const detail = encoder.status === "COMPLETED"
        ? `${encoder.provider || "AI"} · ${Math.round(encoder.confidence_score || 0)}% extraction confidence`
        : `Local processing · AI status: ${String(encoder.status || "unknown").toLowerCase()}`;
      return `<article class="file-item">
        <strong>${escapeHtml(item.document_type.replaceAll("_", " "))}</strong>
        <span>${escapeHtml(detail)}</span>
      </article>`;
    }).join("")
    : `<article class="file-item"><strong>Evidence details unavailable</strong>
       <span>No file-level analysis details were returned.</span></article>`;

  showView("result");
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!queuedPhotos.length && !queuedDocuments.length) {
    evidenceValidation.hidden = false;
    evidenceValidation.scrollIntoView({ behavior: "smooth", block: "center" });
    return;
  }
  analyzeButton.disabled = true;
  showView("loading");
  setProgress(10, "Preparing claim data", "Validating the submitted information");

  try {
    const claim = claimPayload();
    setProgress(20, "Preparing evidence", "Removing files from the previous assessment");
    await api(`/api/v1/claims/${encodeURIComponent(claim.claim_id)}/files`, {
      method: "DELETE",
    });
    setProgress(30, "Registering evidence", "Uploading documents and imagery securely");

    const [photos, documents] = await Promise.all([
      uploadFiles(claim.claim_id, "DAMAGE_PHOTO", queuedPhotos),
      uploadQueuedDocuments(claim.claim_id),
    ]);
    const uploaded = [...photos, ...documents];

    setProgress(55, "Assessing evidence", "Extracting document, image, and semantic indicators");
    const analyses = [];
    for (let index = 0; index < uploaded.length; index += 1) {
      analyses.push(await api(`/api/v1/files/${uploaded[index].file_id}/analyze`, {
        method: "POST",
      }));
      setProgress(
        55 + Math.round(((index + 1) / uploaded.length) * 25),
        "Assessing evidence",
        `Processed ${index + 1} of ${uploaded.length} files`,
      );
    }

    setProgress(88, "Calculating risk profile", "Combining rules, model output, and evidence indicators");
    const result = await api(
      `/api/v1/claims/${encodeURIComponent(claim.claim_id)}/predict-with-files`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(claim),
      },
    );
    setProgress(100, "Assessment complete", "Preparing assessment results");
    renderResult(result, analyses);
  } catch (error) {
    document.querySelector("#errorMessage").textContent = error.message;
    showView("error");
  } finally {
    analyzeButton.disabled = false;
  }
});

checkHealth();
