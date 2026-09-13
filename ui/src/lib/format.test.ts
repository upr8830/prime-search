import { describe, expect, it } from "vitest";

import { JUDGE_SKIPPED, LIMIT_NOTE_GENERIC, STATUS_LABEL, limitNote, noticeText, plainMissing } from "./format";

describe("limit-reached runs (docs/07 §9)", () => {
  it("label a run that reached a limit as completed", () => {
    expect(STATUS_LABEL.budget_exhausted).toBe("completed");
  });

  it("name the limit in plain words", () => {
    expect(limitNote(["max_tokens"])).toBe(
      "ⓘ Research limit reached (processing) — this answer uses the sources found before the limit.",
    );
    expect(limitNote(["max_seconds", "max_tokens"])).toContain("(time, processing)");
  });

  it("fall back to a generic note for runs that did not name the limit", () => {
    expect(limitNote(null)).toBe(LIMIT_NOTE_GENERIC);
    expect(limitNote([])).toBe(LIMIT_NOTE_GENERIC);
    expect(limitNote(["max_unknown"])).toBe(LIMIT_NOTE_GENERIC);
  });

  it("never show engineer words", () => {
    for (const limits of [["max_tokens"], ["max_seconds"], ["max_searches"], ["max_fetches"], ["max_deep_reads"], null]) {
      expect(limitNote(limits)).not.toMatch(/budget|token|max_|\d/i);
    }
  });
});

describe("search tree wording (docs/07 §3)", () => {
  it("calls a retrieval miss skipped and any other task warning a note", () => {
    expect(noticeText({ node: "search_agent:b5", summary: "Couldn't read a page from facebook.com" })).toBe(
      "skipped: couldn't read a page from facebook.com",
    );
    expect(noticeText({ node: "search_agent", summary: "This line of research stopped because of a technical problem" })).toBe(
      "ⓘ This line of research stopped because of a technical problem",
    );
  });

  it("replaces an older run's judge exception in the missing list", () => {
    expect(plainMissing("judge output unusable: RuntimeError: 503")).toBe(JUDGE_SKIPPED);
    expect(plainMissing("the revision date")).toBe("the revision date");
  });
});
