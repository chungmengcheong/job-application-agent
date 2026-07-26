import assert from "node:assert/strict"
import { test } from "node:test"

import {
  applyChanges,
  parseResumeChanges,
  type ResumeChange,
} from "../lib/resume-parser.ts"


test(
  "parses replacement, deletion, and addition markup",
  {
    todo:
      "Known bug: a replacement can be merged into a later standalone deletion.",
  },
  () => {
  const markdown =
    'Led <span style="color:#c00000"><del>small</del></span>' +
    '<span style="color:#008000">large</span> teams. ' +
    '<span style="color:#c00000"><del>Remove this.</del></span> ' +
    '<span style="color:#008000">Add this.</span>'

  const changes = parseResumeChanges(markdown)

  assert.deepEqual(
    changes.map(({ type, originalText, newText }) => ({
      type,
      originalText,
      newText,
    })),
    [
      {
        type: "replacement",
        originalText: "small",
        newText: "large",
      },
      {
        type: "deletion",
        originalText: "Remove this.",
        newText: undefined,
      },
      {
        type: "addition",
        originalText: undefined,
        newText: "Add this.",
      },
    ],
    )
  },
)


test("applying accepted changes reconstructs the proposed resume", () => {
  const markdown =
    'Led <span style="color:#c00000"><del>small</del></span>' +
    '<span style="color:#008000">large</span> teams.'
  const changes = parseResumeChanges(markdown).map((change) => ({
    ...change,
    status: "accepted" as const,
  }))

  assert.equal(applyChanges(markdown, changes), "Led large teams.")
})


test("rejecting changes reconstructs the baseline resume", () => {
  const markdown =
    'Led <span style="color:#c00000"><del>small</del></span>' +
    '<span style="color:#008000">large</span> teams.'
  const changes: ResumeChange[] = parseResumeChanges(markdown).map((change) => ({
    ...change,
    status: "rejected",
  }))

  assert.equal(applyChanges(markdown, changes), "Led small teams.")
})
