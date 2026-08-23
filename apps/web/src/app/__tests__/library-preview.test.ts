/** Previewing a library entry.
 *
 * The question this page is opened with is what a scenario *does*, and
 * until now the only way to find out was to import it, build a
 * deployment on it and open the test bench — three steps and two stored
 * rows to look at a picture.
 */

import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import en from "../../lib/i18n/locales/en.json";
import vi from "../../lib/i18n/locales/vi.json";

const SRC = join(process.cwd(), "src");
const PAGE = readFileSync(join(SRC, "app", "library", "page.tsx"), "utf8");
const PLAYBACK = readFileSync(join(SRC, "lib", "previewPlayback.ts"), "utf8");

describe("previewing writes nothing", () => {
  it("asks a read-only endpoint rather than importing", () => {
    /* The obvious implementation is to import and draw what comes back,
       which is exactly how one database reached 198 maps carrying 41
       distinct checksums. */
    expect(PAGE).toContain("/preview`");
    const preview = PAGE.slice(PAGE.indexOf("const previewEntry"), PAGE.indexOf("const importEntry"));
    expect(preview).not.toContain("method: \"POST\"");
    expect(preview).not.toContain("/import");
  });

  it("is offered without an account", () => {
    /* Looking at a scenario writes nothing, so making somebody sign in
       to look at a picture is a gate on the wrong side of the
       decision. */
    const actions = PAGE.slice(PAGE.indexOf("library-actions"), PAGE.indexOf("</td>", PAGE.indexOf("library-actions")));
    expect(actions).toContain("disabled={previewing !== null}");
    expect(actions).toContain("disabled={!canImport || busy !== null}");
  });

  it("says so on the panel", () => {
    expect(PAGE).toContain("library.previewStoresNothing");
    expect(en).toHaveProperty("library.previewStoresNothing");
    expect(vi).toHaveProperty("library.previewStoresNothing");
  });
});

describe("the preview plays the traffic", () => {
  it("reuses the playback the deployment form uses", () => {
    /* A second way to say "where is the traffic at t" is a second
       answer. */
    expect(PAGE).toContain("trafficAt(preview, playhead)");
    expect(PAGE).toContain("playableSeconds(preview)");
  });

  it("feeds both views one playhead", () => {
    /* Two canvases showing one scenario at two instants would be two
       scenarios. */
    expect(PAGE).toContain("snapshotsOf(preview, playhead)");
  });

  it("takes a narrower type than either reply it is fed", () => {
    /* Neither the validation verdict on one nor the map on the other
       matters to playback, and naming only the fields that do is what
       lets both feed it without a cast. */
    expect(PLAYBACK).toContain("export interface PlayableTraffic");
    expect(PLAYBACK).not.toContain("ScenarioPreview");
  });

  it("offers no scrubber for a scenario with no traffic", () => {
    /* An empty aisle is a thing to look at, not a reason to show a
       control that cannot move. */
    expect(PAGE).toContain("library.previewNoTraffic");
    expect(en).toHaveProperty("library.previewNoTraffic");
    expect(vi).toHaveProperty("library.previewNoTraffic");
  });

  it("parks a new preview at the start", () => {
    /* Otherwise opening a scenario drops the reader into the middle of
       a route they have not watched the beginning of. */
    const preview = PAGE.slice(PAGE.indexOf("const previewEntry"), PAGE.indexOf("const importEntry"));
    expect(preview).toContain("setPlayhead(0)");
    expect(preview).toContain("setPlaying(false)");
  });
});
