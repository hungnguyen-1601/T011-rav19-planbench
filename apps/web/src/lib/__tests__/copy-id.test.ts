/** Copying the id, including the half that usually goes untested.
 *
 * The refusal branch is the reason the write function is a parameter.
 * With `navigator.clipboard` reached for inside, this file could not
 * exist: there is no jsdom here, so the interesting case would be behind
 * a global Node does not have.
 */

import { describe, expect, it, vi } from "vitest";

import { COPY_FEEDBACK_MS, copyDecisionId, copyStateKey } from "@/lib/copyId";

describe("copying", () => {
  it("hands the id to the writer and reports success", async () => {
    const write = vi.fn().mockResolvedValue(undefined);
    await expect(copyDecisionId("20750b0d9dbe", write)).resolves.toBe("copied");
    expect(write).toHaveBeenCalledWith("20750b0d9dbe");
    expect(write).toHaveBeenCalledTimes(1);
  });

  it("reports a refusal as an outcome, not as an exception", async () => {
    /* The clipboard rejects outside a secure context, when the document
       is not focused, and whenever the permission is denied — a page
       opened from `file://` fails every time. Letting that reject would
       print an unhandled rejection in the console of a reader whose only
       fault is having clipboard access switched off. */
    const write = vi.fn().mockRejectedValue(new NotAllowedError());
    await expect(copyDecisionId("20750b0d9dbe", write)).resolves.toBe("failed");
  });

  it("swallows a thrower as well as a rejecter", async () => {
    /* Some browsers throw synchronously when the API is missing rather
       than returning a rejected promise. */
    const write = vi.fn(() => {
      throw new TypeError("navigator.clipboard is undefined");
    });
    await expect(copyDecisionId("x", write)).resolves.toBe("failed");
  });

  it("never rejects, whatever the writer does", async () => {
    for (const write of [
      () => Promise.reject(new Error("denied")),
      () => {
        throw new Error("missing");
      },
      () => Promise.resolve(),
    ]) {
      await expect(copyDecisionId("x", write)).resolves.toMatch(/^(copied|failed)$/);
    }
  });
});

describe("what the button then says", () => {
  it("has a distinct wording for each outcome", () => {
    expect(copyStateKey("copied")).toBe("decisions.detail.copied");
    expect(copyStateKey("failed")).toBe("decisions.detail.copyFailed");
    expect(copyStateKey("copied")).not.toBe(copyStateKey("failed"));
  });

  it("says nothing at rest", () => {
    /* Idle is the id and nothing else. A permanent "Copy" label beside a
       visible id is a word that never changes and never helps. */
    expect(copyStateKey(null)).toBeNull();
  });

  it("holds the confirmation long enough to read", () => {
    expect(COPY_FEEDBACK_MS).toBeGreaterThanOrEqual(2000);
    expect(COPY_FEEDBACK_MS).toBeLessThanOrEqual(6000);
  });
});

class NotAllowedError extends Error {
  constructor() {
    super("Write permission denied.");
    this.name = "NotAllowedError";
  }
}
