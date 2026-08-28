/** Copying a deployment, and correcting one nothing has measured.
 *
 * Filing a deployment took thirty fields and a map, and changing one
 * number meant typing all of it again under a new id — because the
 * server refuses to redefine an id, and refuses for a reason that holds:
 * `episode_context_id` does not hash the environment, so a changed
 * deployment under an old id would leave stored runs describing a world
 * that no longer exists while their ids still matched.
 *
 * That reason is entirely about *stored runs*. A deployment nothing has
 * run has none, so correcting it destroys nothing. These pin both halves
 * — the copy that always works, and the edit that is offered only while
 * it is safe — and the line between them.
 */

import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { suggestProfileId } from "@/lib/decisions";
import en from "../../lib/i18n/locales/en.json";
import viLocale from "../../lib/i18n/locales/vi.json";

const SRC = join(process.cwd(), "src");
const read = (...parts: string[]) => readFileSync(join(SRC, ...parts), "utf8");

const PAGE = read("app", "deployments", "page.tsx");
const FORM = read("components", "DeploymentForm.tsx");
const LIB = read("lib", "decisions.ts");

const dictionaries = en as Record<string, string>;
const vietnamese = viLocale as Record<string, string>;

describe("the id suggested for a copy", () => {
  it("counts up from a trailing number", () => {
    expect(suggestProfileId("sudden_stop_v6", [])).toBe("sudden_stop_v7");
    expect(suggestProfileId("open_hall_2", [])).toBe("open_hall_3");
  });

  it("adds a version to a name that has none", () => {
    expect(suggestProfileId("warehouse", [])).toBe("warehouse_v2");
  });

  it("keeps counting until it finds one that is free", () => {
    /* Duplicating twice must not offer an id already filed: the server
       would refuse it, and the refusal would arrive after the reader had
       edited thirty other fields. */
    expect(suggestProfileId("sudden_stop_v6", ["sudden_stop_v7", "sudden_stop_v8"])).toBe(
      "sudden_stop_v9",
    );
  });

  it("suggests rather than decides", () => {
    // The id goes into every episode_context_id hash and is how somebody
    // recognises this deployment three weeks later. It is filled in and
    // left editable, never assigned behind the reader's back.
    expect(PAGE).toContain("id: suggestProfileId(row.id, profiles.map((each) => each.id))");
  });
});

describe("copying and correcting are different acts", () => {
  it("sends a copy through create and a correction through replace", () => {
    /* A duplicate is a new deployment that happens to start from an old
       one's text. Treating it as an edit would PUT at the id it was
       copied from and overwrite the thing being copied. */
    expect(PAGE).toContain("? await replaceTaskProfile(editing, profile)");
    expect(PAGE).toContain(": await createTaskProfile(profile);");
  });

  it("clears the edit target when a copy is opened", () => {
    /* Opening a copy after opening an edit must not leave `editing`
       pointing at the deployment that was being corrected — the next
       submit would PUT the copy over the thing it was copied from.

       Asserted on the two statements being inside `openCopy`, not on the
       newline between them: pinning a line ending goes red on a checkout
       rather than on a behaviour (CLAUDE.md §6), and my first version of
       this test did exactly that. */
    const openCopy = PAGE.slice(PAGE.indexOf("const openCopy"), PAGE.indexOf("const openEdit"));
    expect(openCopy).toContain("setEditing(null);");
    expect(openCopy).toContain("setOpenedFrom(row.id);");

    const openEdit = PAGE.slice(PAGE.indexOf("const openEdit"), PAGE.indexOf("const file ="));
    expect(openEdit).toContain("setEditing(row.id);");
  });

  it("offers editing only where the server would allow it", () => {
    /* Whether anything was measured is a fact about the run store. The
       server sends it; a count made here would be a second answer, free
       to disagree with the one the PUT is refused on. */
    expect(PAGE).toContain("{profile.editable ? (");
    expect(LIB).toContain("editable?: boolean;");
  });

  it("says why the edit is missing rather than hiding the row's meaning", () => {
    // A row with one button fewer and no explanation reads as a bug.
    expect(PAGE).toContain("deployments.editLockedWhy");
  });
});

describe("the form opened on an existing deployment", () => {
  it("loads its pickers even when a draft arrived first", () => {
    /* The bootstrap used to return early whenever a draft existed, which
       was fine while the only way to have one was for that same effect
       to have made it. Opening the form on a stored deployment breaks
       that: the draft arrives first, and the map, scenario and vehicle
       pickers would stay empty on a form whose whole purpose is to edit
       what they describe. */
    expect(FORM).toContain("listScenarioLibrary().catch(() => [] as LibraryEntry[]),");
    const bootstrap = FORM.slice(FORM.indexOf("The pickers, always"));
    expect(bootstrap.slice(0, bootstrap.indexOf("}, []);"))).not.toContain("if (draft) return;");
  });

  it("still withholds the template when a draft is present", () => {
    // That is the half that would overwrite what was opened.
    expect(FORM).toContain("if (draft) return;");
    expect(FORM).toContain("onDraftChange(withNoiseDefaults(template));");
  });

  it("brings the map controls into line without resetting the missions", () => {
    /* Adopting a map resets the poses onto it, because a coordinate
       means something else on other walls — right when somebody chooses
       a different map, and exactly wrong here: the document already
       carries missions placed on these walls and validated against them.
       Hydration must not call adopt. */
    const hydration = FORM.slice(FORM.indexOf("Bring the map controls into line"));
    const body = hydration.slice(0, hydration.indexOf("}, [draft, startFrom]);"));
    expect(body).toContain("setStoredMapId(custom[1]);");
    expect(body).toContain("setMapData(resource.map_data);");
    expect(body).not.toContain("adopt(");
    expect(body).not.toContain("posesFor");
  });

  it("hydrates once per deployment opened, not on every keystroke", () => {
    // Otherwise typing in the form would drag the map back to whatever
    // the document said when it was opened.
    expect(FORM).toContain("hydratedFrom.current === identity");
    expect(FORM).toContain("hydratedFrom.current = identity;");
  });

  it("leaves a bundled map alone", () => {
    // It has no row in the store to select, and the path it names stays
    // valid. Selecting nothing is the honest answer.
    expect(FORM).toContain("if (!custom) return;");
  });
});

describe("both languages", () => {
  it("answers every key the new controls name", () => {
    for (const key of [
      "deployments.copy",
      "deployments.edit",
      "deployments.editLocked",
      "deployments.editLockedWhy",
    ]) {
      expect(dictionaries[key], `en ${key}`).toBeTruthy();
      expect(vietnamese[key], `vi ${key}`).toBeTruthy();
    }
  });
});
