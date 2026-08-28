/** The map editor's answer to "why did my edit not change what the bench ran?"
 *
 * A deployment names its map by a path carrying the version, so editing
 * a map deliberately leaves every deployment filed before the edit on the
 * old walls. The rule is right — an episode id does not record its map,
 * so moving a deployment would leave its stored results describing a
 * place that no longer exists — and it was invisible. Somebody edited a
 * map, re-ran the bench, and watched it measure the old grid.
 *
 * These pin the two halves that make it visible: the panel states the
 * pinned version, and the only way forward it offers is a **new**
 * deployment, never an edit of the old one.
 */

import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import en from "../../lib/i18n/locales/en.json";
import viLocale from "../../lib/i18n/locales/vi.json";

const SRC = join(process.cwd(), "src");
const read = (...parts: string[]) => readFileSync(join(SRC, ...parts), "utf8");

const PINS = read("components", "MapPins.tsx");
const EDITOR = read("app", "maps", "[id]", "MapEditor.tsx");
const BENCH = read("app", "simulate", "page.tsx");
const API = read("lib", "api.ts");

const dictionaries = en as Record<string, string>;
const vietnamese = viLocale as Record<string, string>;

function keysIn(source: string): string[] {
  return [...new Set([...source.matchAll(/(?<![\w.])t\("([\w.]+)"/g)].map((match) => match[1]))];
}

describe("the pinned-version panel", () => {
  it("asks the server which deployments hold this map", () => {
    expect(API).toContain("mapPins: (mapId: string)");
    expect(API).toContain("/pins`)");
    expect(PINS).toContain("api\n      .mapPins(mapId)");
  });

  it("re-asks after a save, which is when every pin goes stale", () => {
    /* Saving writes a new version, so the deployments that were current
       a moment ago are behind — and that is exactly the moment the
       reader needs telling. A panel keyed only on the map id would still
       be showing "current" for all of them. */
    expect(PINS).toContain("useEffect(reload, [reload, version])");
    expect(EDITOR).toContain("<MapPins mapId={id} version={version} />");
  });

  it("offers a new deployment and never an edit of the old one", () => {
    /* `episode_context_id` does not hash the map, so one id meaning two
       worlds is what would make stored runs unreadable. The server
       refuses it; the panel must not even ask. */
    expect(PINS).toContain("deriveTaskProfile");
    expect(PINS).toContain("new_id: newId.trim()");
    expect(PINS).not.toContain("updateTaskProfile");
    expect(PINS).not.toContain("base_task_profile_id: newId");
  });

  it("will not derive without an id for the new deployment", () => {
    expect(PINS).toContain("disabled={deriving !== null || !newId.trim()}");
  });

  it("offers the move only where it is the answer", () => {
    // A deployment already on the current version has nothing to move
    // to, and a button there would invite a duplicate for no reason.
    expect(PINS).toContain("{pin.stale ? (");
  });

  it("draws nothing when no deployment runs this map", () => {
    // An empty table under a heading says "there is something here".
    expect(PINS).toContain("if (!pins || pins.pins.length === 0) return null;");
  });

  it("shows the server's refusal verbatim", () => {
    /* The refusal worth reading is a mission whose goal now sits inside
       a wall somebody just painted, and it names which mission. */
    expect(PINS).toContain("caught instanceof Error ? caught.message");
  });
});

describe("the test bench says which walls it staged", () => {
  it("keeps the version, not just the grid", () => {
    expect(BENCH).toContain("setStagedMap({ id: resource.id, version: resource.version })");
    expect(BENCH).toContain("bench.mapVersion");
  });
});

describe("both languages", () => {
  it("answers every key these three surfaces name", () => {
    for (const key of [...keysIn(PINS), ...keysIn(EDITOR)]) {
      expect(dictionaries[key], `en ${key}`).toBeTruthy();
      expect(vietnamese[key], `vi ${key}`).toBeTruthy();
    }
    for (const key of ["bench.mapVersion", "maps.pins.behind", "maps.pins.newIdWhy"]) {
      expect(dictionaries[key], `en ${key}`).toBeTruthy();
      expect(vietnamese[key], `vi ${key}`).toBeTruthy();
    }
  });
});
