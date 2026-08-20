// Pure render functions for fit score, rationale, and the gap map - ported
// from extension-panel.tsx's `TabsContent value="review"` block, same
// content/logic, producing an HTML string instead of JSX.

function escapeHtml(text) {
  return String(text ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function fitScoreClass(score) {
  if (typeof score !== "number") return "fit-unknown";
  if (score >= 9) return "fit-excellent";
  if (score >= 7) return "fit-good";
  if (score >= 5) return "fit-fair";
  if (score >= 3) return "fit-poor";
  return "fit-bad";
}

/** @param {{score?: number, rationale?: string}} fit */
export function renderFit(fit) {
  const score = fit?.score;
  const scoreLabel = typeof score === "number" ? `${score}/10` : "N/A";
  return `
    <div class="fit-summary">
      <span class="fit-badge ${fitScoreClass(score)}">${scoreLabel}</span>
      <h2>Job Fit</h2>
    </div>
    <div class="fit-rationale">
      <h3>Rationale</h3>
      <p>${escapeHtml(fit?.rationale || "")}</p>
    </div>
  `;
}

/** @param {Array<{"JD Requirement/Keyword": string, "Present in Resume?": string, "Where/Evidence": string, "Gap handling": string}>} gapMap */
export function renderGapMap(gapMap) {
  if (!gapMap || gapMap.length === 0) {
    return `<h3>Gap Analysis against Job "Must Haves"</h3><p class="muted">No gap analysis available.</p>`;
  }
  const cards = gapMap
    .map(
      (gap) => `
      <div class="gap-card">
        <div class="gap-card-header">
          <span class="gap-keyword">${escapeHtml(gap["JD Requirement/Keyword"])}</span>
          <span class="gap-present gap-present-${escapeHtml(gap["Present in Resume?"]).toLowerCase()}">${escapeHtml(gap["Present in Resume?"])}</span>
        </div>
        <div class="gap-detail"><strong>Evidence:</strong> ${escapeHtml(gap["Where/Evidence"])}</div>
        <div class="gap-detail"><strong>Suggested Action:</strong> ${escapeHtml(gap["Gap handling"])}</div>
      </div>`
    )
    .join("");
  return `<h3>Gap Analysis against Job "Must Haves"</h3><div class="gap-cards">${cards}</div>`;
}

/** @param {string[]} questions */
export function renderQuestionsForm(questions) {
  const items = questions
    .map(
      (question, index) => `
      <div class="question-item">
        <label for="answer-${index}">${index + 1}. ${escapeHtml(question)}</label>
        <textarea id="answer-${index}" data-question-index="${index}" placeholder="Your answer..."></textarea>
      </div>`
    )
    .join("");
  return `
    <div class="questions-form">
      <p class="questions-intro">
        (Optional) I can provide an even more tailored resume if you have additional relevant
        experience and skills. Feel free to skip any question that isn't relevant.
      </p>
      ${items}
    </div>
  `;
}

/**
 * Reads answered questions back out of a rendered question form.
 * @param {HTMLElement} container
 * @param {string[]} questions
 * @returns {Array<{question: string, answer: string}>}
 */
export function collectAnswers(container, questions) {
  return questions.map((question, index) => {
    const field = container.querySelector(`#answer-${index}`);
    return { question, answer: field ? field.value.trim() : "" };
  });
}
