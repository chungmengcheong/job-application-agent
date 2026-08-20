// Ports resume-renderer.tsx's actual redline behavior (the unused
// inline-redline*.tsx files in the retired extension never shipped - see
// plan-refactor-frontend.md's "Current state"): parse the backend's
// deterministic <add>/<del> markup (backend/redline.py), let the user
// accept/reject/edit each change, and render either the decorated redline
// view or the clean (all-pending-changes-accepted) view.
//
// Segments are addressed by array index rather than by re-matching the
// original markup substring. The React version's `tailoredMarkdown.replace
// (originalMarkup, ...)` targeted the first textual match, which is wrong
// when two changes happen to carry identical markup (e.g. the same word
// changed on two different lines) - the documented "known mixed-change
// defect" (docs/frontend.md). Index-based addressing does not have that
// failure mode.

const DEL_RE = /<span style="color:#c00000"><del>([\s\S]*?)<\/del><\/span>/g;
const ADD_RE = /<span style="color:#008000"><add>([\s\S]*?)<\/add><\/span>/g;

// Marks a change's position inline in a plain-text copy of the document so
// headers can be detected per-line before change spans are rendered back in.
// Built via fromCharCode (not a literal escape in source) so the marker is
// an actual NUL character that can never collide with ordinary resume text.
const MARK = String.fromCharCode(0);
const MARK_RE = new RegExp(MARK + "(\\d+)" + MARK, "g");
const markerFor = (index) => `${MARK}${index}${MARK}`;

/**
 * @param {string} markup
 * @returns {Array<{type: "text"|"del"|"add", text: string, status?: "pending"|"accepted"|"rejected", editedText?: string}>}
 */
export function parseSegments(markup) {
  const matches = [
    ...[...markup.matchAll(DEL_RE)].map((m) => ({ index: m.index, length: m[0].length, type: "del", text: m[1] })),
    ...[...markup.matchAll(ADD_RE)].map((m) => ({ index: m.index, length: m[0].length, type: "add", text: m[1] })),
  ].sort((a, b) => a.index - b.index);

  const segments = [];
  let cursor = 0;
  for (const m of matches) {
    if (m.index > cursor) segments.push({ type: "text", text: markup.slice(cursor, m.index) });
    segments.push({ type: m.type, text: m.text, status: "pending" });
    cursor = m.index + m.length;
  }
  if (cursor < markup.length) segments.push({ type: "text", text: markup.slice(cursor) });
  return segments;
}

export function acceptChange(segments, index) {
  segments[index] = { ...segments[index], status: "accepted" };
}

export function rejectChange(segments, index) {
  segments[index] = { ...segments[index], status: "rejected" };
}

export function editChange(segments, index, newText) {
  segments[index] = { ...segments[index], status: "accepted", editedText: newText };
}

function finalText(seg) {
  if (seg.type === "text") return seg.text;
  if (seg.status === "rejected") return seg.type === "del" ? seg.text : "";
  const text = seg.editedText ?? seg.text;
  return seg.type === "del" ? "" : text;
}

/** @returns {string} the resume text with every change resolved (pending treated as accepted). */
export function cleanText(segments) {
  return segments.map(finalText).join("");
}

function escapeHtml(text) {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function renderInline(text) {
  return escapeHtml(text).replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");
}

function changeSpanHtml(seg, index, showRedlines) {
  if (!showRedlines || seg.status !== "pending") {
    return renderInline(finalText(seg));
  }
  const label = seg.type === "del" ? "redline-del" : "redline-add";
  const toolbar =
    seg.type === "del"
      ? `<span class="toolbar">
           <button type="button" data-action="accept" data-index="${index}" title="Accept deletion (remove text)">Accept</button>
           <button type="button" data-action="reject" data-index="${index}" title="Reject deletion (keep text)">Reject</button>
         </span>`
      : `<span class="toolbar">
           <button type="button" data-action="accept" data-index="${index}" title="Accept addition (keep text)">Accept</button>
           <button type="button" data-action="edit" data-index="${index}" title="Edit text">Edit</button>
           <button type="button" data-action="reject" data-index="${index}" title="Reject addition (remove text)">Reject</button>
         </span>`;
  return `<span class="redline-change ${label}" data-index="${index}">${renderInline(seg.text)}${toolbar}</span>`;
}

/**
 * Renders segments into `container` and (re)binds its click/edit handlers.
 * Safe to call repeatedly - handlers are assigned via element properties
 * (`.onclick`, etc.), which overwrite rather than accumulate.
 *
 * @param {HTMLElement} container
 * @param {Array} segments
 * @param {{showRedlines: boolean, editingIndex: number|null, onChange: (patch: object) => void}} opts
 */
export function renderRedline(container, segments, { showRedlines, editingIndex, onChange }) {
  const markedDoc = segments.map((seg, i) => (seg.type === "text" ? seg.text : markerFor(i))).join("");

  const html = markedDoc
    .split("\n")
    .map((line) => {
      let tag = "div";
      let content = line;
      if (line.startsWith("## ")) {
        tag = "h2";
        content = line.slice(3);
      } else if (line.startsWith("# ")) {
        tag = "h1";
        content = line.slice(2);
      }
      if (!content.trim()) return "<br>";

      const rendered = content.replace(MARK_RE, (_, indexStr) => {
        const index = Number(indexStr);
        const seg = segments[index];
        if (index === editingIndex) {
          return `<span class="redline-change redline-editing" data-index="${index}" contenteditable="true" spellcheck="false">${escapeHtml(seg.editedText ?? seg.text)}</span>`;
        }
        return changeSpanHtml(seg, index, showRedlines);
      });
      return `<${tag}>${rendered}</${tag}>`;
    })
    .join("");

  container.innerHTML = html;

  container.onclick = (event) => {
    const button = event.target.closest("button[data-action]");
    if (!button) return;
    const index = Number(button.dataset.index);
    const action = button.dataset.action;
    if (action === "accept") acceptChange(segments, index);
    else if (action === "reject") rejectChange(segments, index);
    else if (action === "edit") {
      onChange({ editingIndex: index });
      return;
    }
    onChange({ editingIndex: null });
  };

  const commitEdit = (el) => {
    const index = Number(el.dataset.index);
    editChange(segments, index, el.textContent);
    onChange({ editingIndex: null });
  };

  container.onfocusout = (event) => {
    const el = event.target.closest(".redline-editing");
    if (el) commitEdit(el);
  };

  container.onkeydown = (event) => {
    const el = event.target.closest(".redline-editing");
    if (!el) return;
    if (event.key === "Enter") {
      event.preventDefault();
      commitEdit(el);
    } else if (event.key === "Escape") {
      event.preventDefault();
      onChange({ editingIndex: null });
    }
  };

  if (editingIndex !== null) {
    container.querySelector(".redline-editing")?.focus();
  }
}
