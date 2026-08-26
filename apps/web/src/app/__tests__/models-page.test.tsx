/** The model registry page.
 *
 * No jsdom in this repo, so what is checked is everything that would
 * still be wrong if the markup were perfect: the route the sidebar
 * points at exists, no delete is offered, both kinds of "unusable" stay
 * apart, and every translation key it names is in both locales.
 */

import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import en from "../../lib/i18n/locales/en.json";
import vi from "../../lib/i18n/locales/vi.json";

const SRC = join(process.cwd(), "src");
const PAGE = readFileSync(join(SRC, "app", "models", "page.tsx"), "utf8");
const NAV = readFileSync(join(SRC, "lib", "navigation.ts"), "utf8");
const CSS = readFileSync(join(SRC, "app", "globals.css"), "utf8");

describe("the sidebar entry now leads somewhere", () => {
  it("has a route for every href the navigation offers", () => {
    /* `/models` was the one entry with no page behind it: the API, the
       tables, the client contract and forty-eight translation keys in
       both languages all existed, and clicking it produced a 404. */
    expect(NAV).toContain('href: "/models"');
    expect(PAGE).toContain("export default function ModelsPage");
  });
});

describe("what the page will and will not do", () => {
  it("offers no delete", () => {
    /* **A decision, not an omission.** `DELETE /models/{id}` exists.
       A model here is what a benchmark *ran* — results are filed
       against its id — so removing the row turns those measurements
       into records of nothing. Disabling retires it honestly: the id
       keeps resolving and the history keeps meaning what it said. */
    expect(PAGE).not.toContain("deleteModel");
    expect(PAGE).not.toContain("models.deleteConfirm");
  });

  it("uploads and toggles, which is the scope it was built for", () => {
    expect(PAGE).toContain("uploadModel(");
    expect(PAGE).toContain("setModelStatus(");
  });

  it("keeps a decision apart from a verdict about the file", () => {
    /* `status` is what somebody chose; `validation_status` is what the
       zip turned out to be. A disabled model that validated cleanly and
       an active model whose file will not load are both unusable and
       need opposite actions. */
    expect(PAGE).toContain("models.status.${model.status}");
    expect(PAGE).toContain("models.validation.${model.validation_status}");
  });

  it("does not paint an unchecked file as a fault", () => {
    /* Nothing is wrong with a model nobody has validated yet. Amber
       there files an absence as a failure. */
    const tone = PAGE.slice(PAGE.indexOf("VALIDATION_TONE"), PAGE.indexOf("export default"));
    expect(tone).toContain('pending: "muted-badge"');
    expect(tone).toContain('failed: "err"');
  });

  it("shows a model somebody else owns without offering its controls", () => {
    /* The server enforces this; a button that answers with a 403 is a
       control that lied about being available. */
    expect(PAGE).toContain("model.is_owner ?");
    expect(PAGE).toContain("models.notOwner");
  });

  it("dims a retired model rather than hiding it", () => {
    /* It is still the model a past benchmark ran, and a reader chasing
       a result has to be able to find it. */
    expect(CSS).toContain(".models-page tr.is-unusable td");
    expect(PAGE).toContain("isUsable(model)");
  });
});

describe("uploading", () => {
  it("checks the extension before sending the file", () => {
    /* The server checks too and its message is the one that matters,
       but learning that a `.pth` is not a `.zip` after 200 MB is a
       refusal that cost the whole transfer to deliver. */
    expect(PAGE).toContain("extensionOf(file.name)");
    expect(PAGE).toContain("models.wrongExtension");
  });

  it("reports progress", () => {
    /* A large checkpoint on a slow connection with nothing moving looks
       exactly like a hung page — the reason `lib/models.ts` uses
       XMLHttpRequest rather than fetch at all. */
    expect(PAGE).toContain("setPercent");
    expect(PAGE).toContain("models-progress");
  });

  it("keeps the three files as three controls", () => {
    /* The zip is the only thing that can be executed, the json is
       parsed and validated, the pdf is prose and is never read as
       configuration. One "attachments" picker would lose that. */
    expect(PAGE).toContain("ACCEPTED.model");
    expect(PAGE).toContain("ACCEPTED.metadata");
    expect(PAGE).toContain("ACCEPTED.document");
  });

  it("will not send without the parts the server requires", () => {
    expect(PAGE).toContain("const ready =");
    expect(PAGE).toContain("disabled={!ready || percent !== null}");
  });
});

describe("translation keys", () => {
  const keys = [...PAGE.matchAll(/t\(\s*"([a-zA-Z0-9_.]+)"/g)].map((hit) => hit[1]);

  it("names enough of them to be this page", () => {
    expect(new Set(keys).size).toBeGreaterThan(15);
  });

  it.each([...new Set(keys)])("%s exists in both locales", (key) => {
    expect(en).toHaveProperty(key);
    expect(vi).toHaveProperty(key);
  });

  it.each(["pending", "structural", "loaded", "failed"])(
    "models.validation.%s exists in both locales",
    (status) => {
      /* Composed at runtime from the record, so no static scan of the
         source would catch a missing one. */
      expect(en).toHaveProperty(`models.validation.${status}`);
      expect(vi).toHaveProperty(`models.validation.${status}`);
    },
  );

  it.each(["active", "disabled"])("models.status.%s exists in both locales", (status) => {
    expect(en).toHaveProperty(`models.status.${status}`);
    expect(vi).toHaveProperty(`models.status.${status}`);
  });
});

describe("the page carries two modes", () => {
  const LIB = readFileSync(join(SRC, "lib", "models.ts"), "utf8");
  const AUTH = readFileSync(join(SRC, "lib", "auth.ts"), "utf8");

  it("drops the prose that answered a question asked once", () => {
    /* Three paragraphs — what a PPO model is, what to upload, and that
       training is not built yet — sat above the form on every visit.
       What survives is the hint on the file picker, where the question
       is actually asked. */
    expect(PAGE).not.toContain("models.subtitle");
    expect(PAGE).not.toContain("models.trainingNote");
    expect(PAGE).toContain("models.fileHint");
  });

  it("is called Models rather than Model Registry", () => {
    expect((en as Record<string, string>)["nav.models"]).toBe("Models");
    expect((en as Record<string, string>)["models.title"]).toBe("Models");
  });

  it("separates filing a new artefact from editing one on the shelf", () => {
    /* One form that sometimes creates and sometimes mutates depending on
       a field set five fields ago is two behaviours wearing one button. */
    expect(PAGE).toContain('id: "upload" as const');
    expect(PAGE).toContain('id: "edit" as const');
    expect(PAGE).toContain("function EditPanel(");
  });

  it("edits only the labels, never the artefact", () => {
    /* `POST /models/{id}/documents` refuses a `model` kind outright, and
       that refusal is the rule that also keeps a benchmarked model from
       being deleted. */
    expect(LIB).toContain("export interface ModelEdits");
    expect(LIB).toContain('kind: "metadata" | "document"');
    expect(LIB).not.toContain('kind: "model"');
  });

  it("says the zip is fixed instead of offering a picker that fails", () => {
    /* A control that collects 200 MB and then reports that this was
       never allowed is a worse answer than the sentence. */
    expect(PAGE).toContain("models.edit.fileFixed");
    expect(PAGE).toContain("models-file--fixed");
    const fixed = PAGE.slice(PAGE.indexOf("models-file--fixed"));
    expect(fixed.slice(0, fixed.indexOf("</div>"))).not.toContain('type="file"');
  });

  it("hands the labels to the upload form for a new version", () => {
    /* Otherwise "upload as a new version" means retyping seven fields
       that are already on screen. */
    expect(PAGE).toContain("onNewVersion");
    expect(PAGE).toContain("setPrefill(model)");
    expect(PAGE).toContain("prefill?: ModelSummary | null;");
  });

  it("leaves the version for the author to bump", () => {
    /* Filling it in would guess at a numbering scheme nobody
       declared. */
    const carried = PAGE.slice(PAGE.indexOf("if (!prefill) return;"));
    expect(carried.slice(0, carried.indexOf("}, [prefill])"))).not.toContain("setVersion(");
  });

  it("offers only models this account owns", () => {
    /* The server enforces it; a picker offering the rest would collect a
       form and answer with a 403. */
    expect(PAGE).toContain("models.filter((model) => model.is_owner)");
  });

  it("refollows the fields when the selection changes", () => {
    /* Otherwise switching models leaves the previous one's name in the
       box and the next save writes it onto the wrong record. */
    expect(PAGE).toContain("}, [chosen?.id]);");
  });

  it("lets a multipart body set its own content type", () => {
    /* The boundary is generated per request and only `fetch` knows it.
       Declaring JSON over a FormData sends a body the server cannot
       parse, and the failure reads as a rejected file. */
    expect(AUTH).toContain("init?.body instanceof FormData");
  });
});
