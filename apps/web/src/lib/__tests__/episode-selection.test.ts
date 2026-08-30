/** Which episode a floating component may attach a question to.
 *
 * Three wrong versions this guards, each of which would look right on
 * screen: publish the episode the replay opened on, keep a selection
 * after the reader walked to another run, or keep one after the page
 * that owned it went away.
 */

import { readFileSync } from "node:fs";
import { join } from "node:path";

import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  clearEpisodeSelection,
  episodeForRun,
  getEpisodeSelection,
  setEpisodeSelection,
  subscribeEpisodeSelection,
} from "../episodeSelection";

beforeEach(() => {
  clearEpisodeSelection();
});

describe("publishing a selection", () => {
  it("starts empty, because nobody has chosen anything", () => {
    expect(getEpisodeSelection()).toEqual({ runId: "", episodeContextId: "" });
  });

  it("carries the run as well as the episode", () => {
    setEpisodeSelection({ runId: "r-1", episodeContextId: "ep-004" });
    expect(getEpisodeSelection()).toEqual({ runId: "r-1", episodeContextId: "ep-004" });
  });

  it("tells subscribers once per change", () => {
    const listener = vi.fn();
    const unsubscribe = subscribeEpisodeSelection(listener);
    setEpisodeSelection({ runId: "r-1", episodeContextId: "ep-004" });
    setEpisodeSelection({ runId: "r-1", episodeContextId: "ep-004" });
    unsubscribe();
    expect(listener).toHaveBeenCalledTimes(1);
  });

  it("stops telling a subscriber that unsubscribed", () => {
    const listener = vi.fn();
    subscribeEpisodeSelection(listener)();
    setEpisodeSelection({ runId: "r-1", episodeContextId: "ep-004" });
    expect(listener).not.toHaveBeenCalled();
  });
});

describe("attaching it to a question", () => {
  it("attaches the episode a reader chose on this run", () => {
    const selection = { runId: "r-1", episodeContextId: "ep-004" };
    expect(episodeForRun("r-1", selection)).toBe("ep-004");
  });

  it("attaches nothing on a run nobody has chosen from", () => {
    expect(episodeForRun("r-1", { runId: "", episodeContextId: "" })).toBe("");
  });

  it("attaches nothing when the selection belongs to another run", () => {
    // The moment between walking to a new run's page and choosing an
    // episode on it. The id is still the previous page's, and sending
    // it would put the model in front of the wrong record.
    const stale = { runId: "r-0", episodeContextId: "ep-004" };
    expect(episodeForRun("r-1", stale)).toBe("");
  });

  it("attaches nothing off a run's page at all", () => {
    const selection = { runId: "r-1", episodeContextId: "ep-004" };
    expect(episodeForRun("", selection)).toBe("");
  });
});

describe("what it deliberately does not do", () => {
  it("keeps nothing in storage", () => {
    // A selection that survived a reload would attach the next question
    // to an episode chosen before it, with nothing on screen saying so.
    // Read off the source rather than asserted about behaviour: there is
    // no jsdom here, so the alternative is a test that cannot tell a
    // module using localStorage from one that does not.
    // Comments stripped first. This module explains in prose *why* it
    // does not use `localStorage`, and a test reading the raw file would
    // fail on the explanation — the same trap `tokens.test.ts` documents
    // for a token named inside a comment.
    const source = readFileSync(
      join(process.cwd(), "src", "lib", "episodeSelection.ts"),
      "utf8",
    )
      .replace(/\/\*[\s\S]*?\*\//g, "")
      .replace(/\/\/.*$/gm, "");
    expect(source).not.toContain("localStorage");
    expect(source).not.toContain("sessionStorage");
    expect(source).not.toContain("createPersistedStore");
  });

  it("is published from one place only", () => {
    // Called from `chooseEpisode` and nowhere else. Publishing from the
    // effect that loads the replay would publish the episode it opened
    // on, which nobody chose.
    const page = readFileSync(
      join(process.cwd(), "src", "app", "decisions", "[id]", "DecisionDetail.tsx"),
      "utf8",
    );
    const calls = page.match(/setEpisodeSelection\(/g) ?? [];
    expect(calls).toHaveLength(1);
    expect(page).toContain("clearEpisodeSelection");
  });

  it("clears back to empty", () => {
    setEpisodeSelection({ runId: "r-1", episodeContextId: "ep-004" });
    clearEpisodeSelection();
    expect(getEpisodeSelection()).toEqual({ runId: "", episodeContextId: "" });
  });
});
