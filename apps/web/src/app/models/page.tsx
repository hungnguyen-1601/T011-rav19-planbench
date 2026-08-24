"use client";

/** The model registry — trained policies the platform can run.
 *
 * **The page the sidebar had been advertising.** `/models` was the one
 * navigation entry with no route behind it: the API, the tables and the
 * whole client contract in `lib/models.ts` were built, forty-eight
 * translation keys were written in both languages, and the page itself
 * never was. Clicking it produced a 404.
 *
 * **No delete button, and that is a decision rather than an omission.**
 * `DELETE /models/{id}` exists and this page does not call it. A model
 * here is what a benchmark *ran*: results are filed against its id, and
 * removing the row turns those measurements into records of nothing —
 * the same rule that makes a deployment with runs refuse to delete and
 * a map a simulation names refuse to be swept. Disabling is the honest
 * retirement: the id keeps resolving, the history keeps meaning what it
 * said, and the model stops being offered for new work.
 *
 * **Two kinds of "not usable", kept apart.** `status` is a decision
 * somebody made; `validation_status` is what the file turned out to be.
 * A disabled model that validated cleanly and an active model whose zip
 * would not load are both unusable and need opposite actions, so they
 * are two columns rather than one verdict.
 */

import { useCallback, useEffect, useState } from "react";

import { EmptyState } from "@/components/EmptyState";
import { Tabs } from "@/components/Tabs";
import { Hint } from "@/components/Hint";
import { Icon } from "@/components/Icon";
import { useSession } from "@/lib/auth";
import {
  ACCEPTED,
  type ModelSummary,
  type RobotProfile,
  extensionOf,
  formatSize,
  isUsable,
  attachDocument,
  listModels,
  listRobotProfiles,
  revalidateModel,
  setModelStatus,
  updateModel,
  uploadModel,
} from "@/lib/models";
import {
  type PluginBundleSummary,
  blockedReason,
  listPlugins,
  revalidatePlugin,
  setPluginStatus,
  stackIdFor,
} from "@/lib/plugins";
import { PluginImportPanel } from "@/components/PluginImportPanel";
import { useTranslation } from "@/lib/i18n";

/** Tone for a validation verdict.
 *
 * `pending` is deliberately not a warning. Nothing is wrong with a file
 * nobody has checked yet — painting it amber files an absence as a
 * fault, which is the same mistake the evidence panel refuses to make
 * with an unrun detector.
 */
const VALIDATION_TONE: Record<string, string> = {
  pending: "muted-badge",
  structural: "ok",
  loaded: "ok",
  failed: "err",
};

export default function ModelsPage() {
  const { t } = useTranslation();
  const session = useSession();
  const [models, setModels] = useState<ModelSummary[]>([]);
  const [profiles, setProfiles] = useState<RobotProfile[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  /** Which row has a request in flight, so one button spins rather than
   *  the whole table freezing. */
  const [busy, setBusy] = useState<string | null>(null);
  const [mode, setMode] = useState<"upload" | "edit" | "import">("upload");
  const [plugins, setPlugins] = useState<PluginBundleSummary[]>([]);
  /** A model whose file cannot be replaced, carried into the upload form
   *  so "upload as a new version" does not mean retyping seven fields. */
  const [prefill, setPrefill] = useState<ModelSummary | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      // Profiles come with the list rather than on demand: the upload
      // form needs them before anybody opens it, and a robot profile
      // picker that populates a second after the form appears is a
      // picker somebody has already tried to use.
      const [uploaded, robots, imported] = await Promise.all([
        listModels(),
        listRobotProfiles(),
        listPlugins(),
      ]);
      setModels(uploaded);
      setProfiles(robots);
      setPlugins(imported);
      setError(null);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const toggle = async (model: ModelSummary) => {
    setBusy(model.id);
    try {
      const next = await setModelStatus(model.id, model.status === "active" ? "disabled" : "active");
      setModels((current) => current.map((row) => (row.id === next.id ? next : row)));
      setError(null);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setBusy(null);
    }
  };

  const togglePlugin = async (bundle: PluginBundleSummary) => {
    setBusy(bundle.id);
    try {
      const next = await setPluginStatus(
        bundle.id,
        bundle.status === "active" ? "disabled" : "active",
      );
      setPlugins((current) => current.map((row) => (row.id === next.id ? next : row)));
      setError(null);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setBusy(null);
    }
  };

  const recheckPlugin = async (bundle: PluginBundleSummary) => {
    setBusy(bundle.id);
    try {
      const next = await revalidatePlugin(bundle.id);
      setPlugins((current) => current.map((row) => (row.id === next.id ? next : row)));
      setError(null);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setBusy(null);
    }
  };

  const recheck = async (model: ModelSummary) => {
    setBusy(model.id);
    try {
      const next = await revalidateModel(model.id);
      setModels((current) => current.map((row) => (row.id === next.id ? next : row)));
      setError(null);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setBusy(null);
    }
  };

  return (
    <section className="models-page">
      {/* **The prose that was here is gone.** Three paragraphs — what a
          PPO model is, what to upload, and that training is not built
          yet — sat above the form on every visit, and they answer
          questions somebody asks once. What survives of them is the hint
          on the file picker, which is where the question is actually
          asked. */}
      <div className="page-head">
        <div>
          <h1>{t("models.title")}</h1>
        </div>
        <span className="badge muted-badge">
          {loading ? "—" : models.length}
        </span>
      </div>

      {error ? <div className="error-box">{error}</div> : null}

      {/* **Two modes, because they are two different acts.** Uploading
          files a new artefact; editing changes what is written *about*
          one already on the shelf. Putting the second inside the first
          would mean a form that sometimes creates and sometimes mutates
          depending on a field somebody set five fields ago. */}
      {session ? (
        <div className="panel models-modes">
          <Tabs
            tabs={[
              {
                id: "upload" as const,
                label: t("models.mode.upload"),
                content: (
                  <UploadPanel
                    profiles={profiles}
                    prefill={prefill}
                    onUploaded={() => void refresh()}
                  />
                ),
              },
              {
                id: "import" as const,
                label: t("models.mode.import"),
                content: (
                  <PluginImportPanel profiles={profiles} onImported={() => void refresh()} />
                ),
              },
              {
                id: "edit" as const,
                label: t("models.mode.edit"),
                content: (
                  <EditPanel
                    models={models}
                    profiles={profiles}
                    onChanged={(next) =>
                      setModels((current) =>
                        current.map((row) => (row.id === next.id ? next : row)),
                      )
                    }
                    onNewVersion={(model) => {
                      setPrefill(model);
                      setMode("upload");
                    }}
                  />
                ),
              },
            ]}
            active={mode}
            onSelect={setMode}
            idPrefix="models"
            ariaLabel={t("models.title")}
          />
        </div>
      ) : (
        <div className="panel">
          <p className="muted">{t("deployments.file.signedOut")}</p>
        </div>
      )}

      {loading ? (
        <p className="muted">{t("common.loading")}</p>
      ) : models.length === 0 ? (
        <EmptyState icon="library" title={t("models.empty.title")} body={t("models.empty.body")} />
      ) : (
        <div className="panel">
          <div className="table-scroll wide">
            <table>
              <thead>
                <tr>
                  <th>{t("models.name")}</th>
                  <th>{t("models.robotProfile")}</th>
                  <th>{t("models.size")}</th>
                  <th>{t("models.validation.pending")}</th>
                  <th>{t("models.status.active")}</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {models.map((model) => (
                  <ModelRow
                    key={model.id}
                    model={model}
                    profiles={profiles}
                    busy={busy === model.id}
                    onToggle={() => void toggle(model)}
                    onRecheck={() => void recheck(model)}
                  />
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
      {plugins.length > 0 ? (
        <div className="panel">
          <div className="panel-head">
            <h3>{t("plugins.listTitle")}</h3>
          </div>
          {/* **A separate table, not extra rows in the models one.** They
              are unusable in different ways and fixed by different acts:
              a model fails on a shape, an algorithm fails on a capability
              this deployment does not offer. One table would need a
              column that means two things. */}
          <div className="table-scroll wide">
            <table>
              <thead>
                <tr>
                  <th>{t("models.name")}</th>
                  <th>{t("plugins.pluginId")}</th>
                  <th>{t("plugins.requires")}</th>
                  <th>{t("models.validation.pending")}</th>
                  <th>{t("models.status.active")}</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {plugins.map((bundle) => (
                  <PluginRow
                    key={bundle.id}
                    bundle={bundle}
                    busy={busy === bundle.id}
                    onToggle={() => void togglePlugin(bundle)}
                    onRecheck={() => void recheckPlugin(bundle)}
                  />
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}
    </section>
  );
}

/** One imported algorithm.
 *
 * The stack id is shown because it is what a benchmark names and what a
 * report will quote — a row that showed only the display name would
 * leave somebody holding a result they could not match to a row here.
 */
function PluginRow({
  bundle,
  busy,
  onToggle,
  onRecheck,
}: {
  bundle: PluginBundleSummary;
  busy: boolean;
  onToggle: () => void;
  onRecheck: () => void;
}) {
  const { t } = useTranslation();
  const blocked = blockedReason(bundle);

  return (
    <tr className={blocked ? "is-unusable" : undefined}>
      <td>
        <strong>{bundle.name}</strong> <span className="muted">v{bundle.version}</span>
        {bundle.description ? <div className="muted small">{bundle.description}</div> : null}
        <div className="muted small">
          {t("plugins.stackId")}: <code>{stackIdFor(bundle)}</code>
        </div>
      </td>
      <td>
        <code className="small">{bundle.plugin_id}</code>
        <div className="muted small">
          {bundle.role} · v{bundle.plugin_version}
        </div>
      </td>
      <td>
        <code className="small">{bundle.requirements.join(", ") || "—"}</code>
      </td>
      <td>
        <span className={`badge ${VALIDATION_TONE[bundle.validation_status] ?? "muted-badge"}`}>
          {t(`models.validation.${bundle.validation_status}`)}
        </span>
        {bundle.validation_message ? (
          <div className="muted small">{bundle.validation_message}</div>
        ) : null}
      </td>
      <td>
        <span className={`badge ${bundle.status === "active" ? "ok" : "muted-badge"}`}>
          {t(`models.status.${bundle.status}`)}
        </span>
        {blocked ? (
          <div className="muted small">{t(`plugins.blocked.${blocked}`)}</div>
        ) : null}
      </td>
      <td className="row-actions">
        <button type="button" disabled={busy} onClick={onRecheck}>
          {t("plugins.recheck")}
        </button>
        <button type="button" disabled={busy} onClick={onToggle}>
          {bundle.status === "active" ? t("models.disable") : t("models.enable")}
        </button>
      </td>
    </tr>
  );
}

function ModelRow({
  model,
  profiles,
  busy,
  onToggle,
  onRecheck,
}: {
  model: ModelSummary;
  profiles: RobotProfile[];
  busy: boolean;
  onToggle: () => void;
  onRecheck: () => void;
}) {
  const { t } = useTranslation();
  const profile = profiles.find((entry) => entry.id === model.robot_profile_id);

  return (
    <tr className={isUsable(model) ? undefined : "is-unusable"}>
      <td>
        <strong>{model.name}</strong> <span className="muted">v{model.version}</span>
        {model.is_owner ? (
          <span className="badge muted-badge models-owner">{t("models.owner")}</span>
        ) : null}
        {model.description ? <div className="muted small">{model.description}</div> : null}
        {/* The observation and action shapes, because a model that will
            not run usually fails on one of them and the number is the
            answer rather than the word "incompatible". */}
        <div className="muted small models-shapes">
          {t("models.observation")}: <code>{model.observation_schema.shape.join("×") || "—"}</code>
          {" · "}
          {t("models.action")}: <code>{model.action_schema.shape.join("×") || "—"}</code>
        </div>
      </td>
      <td>
        {/* The profile's name, with its id kept beside it: the id is
            what the upload named and what a support question will
            quote. */}
        {profile ? profile.name : "—"}{" "}
        <code className="muted small">{model.robot_profile_id}</code>
      </td>
      <td className="num">{formatSize(model.file_size)}</td>
      <td>
        <span className={`badge ${VALIDATION_TONE[model.validation_status] ?? "muted-badge"}`}>
          {t(`models.validation.${model.validation_status}`)}
        </span>
        {model.validation_message ? (
          <div className="muted small">{model.validation_message}</div>
        ) : null}
      </td>
      <td>
        <span className={`badge ${model.status === "active" ? "ok" : "muted-badge"}`}>
          {t(`models.status.${model.status}`)}
        </span>
      </td>
      <td className="models-actions">
        {/* **Only the owner may change it.** The server enforces this;
            the page says so rather than offering a button that answers
            with a 403. */}
        {model.is_owner ? (
          <>
            <button type="button" disabled={busy} onClick={onToggle}>
              {t(model.status === "active" ? "models.disable" : "models.enable")}
            </button>
            <button type="button" disabled={busy} onClick={onRecheck}>
              {t("models.recheck")}
            </button>
          </>
        ) : (
          <span className="muted small">{t("models.notOwner")}</span>
        )}
      </td>
    </tr>
  );
}

/** Upload: five fields, three files, and a progress bar that is the
 *  reason this does not go through `fetch`.
 *
 * A 200 MB checkpoint on a slow connection with no progress reported
 * looks exactly like a hung page, and `fetch` still cannot report upload
 * progress. `lib/models.ts` uses `XMLHttpRequest` for that alone.
 */
function UploadPanel({
  profiles,
  prefill,
  onUploaded,
}: {
  profiles: RobotProfile[];
  /** A model somebody asked to re-upload. Its labels are copied in and
   *  its version is left for the author to bump: filling that in too
   *  would guess at a numbering scheme nobody declared. */
  prefill?: ModelSummary | null;
  onUploaded: () => void;
}) {
  const { t } = useTranslation();
  const [name, setName] = useState("");
  const [version, setVersion] = useState("1");
  const [description, setDescription] = useState("");
  const [frameworkVersion, setFrameworkVersion] = useState("");
  const [robotProfileId, setRobotProfileId] = useState("");
  const [trainingEnvironment, setTrainingEnvironment] = useState("");
  const [modelFile, setModelFile] = useState<File | null>(null);
  const [metadataFile, setMetadataFile] = useState<File | null>(null);
  const [documentFile, setDocumentFile] = useState<File | null>(null);
  const [percent, setPercent] = useState<number | null>(null);
  const [refusal, setRefusal] = useState<string | null>(null);

  // The picker opens on the first profile rather than on an empty
  // option: every model needs one, and a select that starts blank is a
  // field somebody can miss and a 422 they then have to read.
  useEffect(() => {
    if (!robotProfileId && profiles.length > 0) setRobotProfileId(profiles[0].id);
  }, [profiles, robotProfileId]);

  /* Carried over from "upload as a new version": everything except the
     files and the version, which are the two things that make it a new
     version rather than a copy. */
  useEffect(() => {
    if (!prefill) return;
    setName(prefill.name);
    setDescription(prefill.description);
    setFrameworkVersion("");
    setRobotProfileId(prefill.robot_profile_id);
    setTrainingEnvironment(prefill.training_environment);
  }, [prefill]);

  /** Refuse the wrong extension here rather than after the upload.
   *
   * The server checks too and its message is the one that matters, but
   * finding out that a `.pth` is not a `.zip` after sending 200 MB is a
   * refusal that cost the whole transfer to deliver. */
  const choose = (
    file: File | null,
    expected: string,
    set: (value: File | null) => void,
  ) => {
    setRefusal(null);
    if (!file) {
      set(null);
      return;
    }
    const actual = extensionOf(file.name);
    if (actual !== expected) {
      set(null);
      setRefusal(t("models.wrongExtension", { expected, actual: actual || "—" }));
      return;
    }
    set(file);
  };

  const ready = name.trim() !== "" && robotProfileId !== "" && modelFile !== null;

  const submit = async () => {
    if (!modelFile || !ready) return;
    setPercent(0);
    setRefusal(null);
    try {
      await uploadModel(
        {
          name,
          version,
          description,
          framework: "stable-baselines3",
          frameworkVersion,
          robotProfileId,
          trainingEnvironment,
          modelFile,
          metadataFile,
          documentFile,
        },
        setPercent,
      );
      setName("");
      setDescription("");
      setModelFile(null);
      setMetadataFile(null);
      setDocumentFile(null);
      onUploaded();
    } catch (caught) {
      setRefusal(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setPercent(null);
    }
  };

  return (
    <div className="panel models-upload">
      <div className="panel-head">
        <h3>
          <span className="panel-title-icon" aria-hidden="true">
            <Icon name="plus" size={17} />
          </span>
          {t("models.upload")}
        </h3>
      </div>

      <div className="models-upload-grid">
        <label className="field">
          <span>{t("models.name")}</span>
          <input value={name} onChange={(event) => setName(event.target.value)} />
        </label>
        <label className="field">
          <span>{t("models.version")}</span>
          <input value={version} onChange={(event) => setVersion(event.target.value)} />
        </label>
        <label className="field">
          <span>{t("models.robotProfile")}</span>
          <select
            value={robotProfileId}
            onChange={(event) => setRobotProfileId(event.target.value)}
          >
            {profiles.map((profile) => (
              <option key={profile.id} value={profile.id}>
                {profile.name} · {profile.lidar_beams} beams
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>{t("models.frameworkVersion")}</span>
          <input
            value={frameworkVersion}
            onChange={(event) => setFrameworkVersion(event.target.value)}
          />
        </label>
        <label className="field models-upload-wide">
          <span>{t("models.description")}</span>
          <input value={description} onChange={(event) => setDescription(event.target.value)} />
        </label>
        <label className="field models-upload-wide">
          <span>{t("models.trainingEnvironment")}</span>
          <input
            value={trainingEnvironment}
            onChange={(event) => setTrainingEnvironment(event.target.value)}
          />
        </label>
      </div>

      {/* Three files and three different meanings, said on each one.
          The zip is the only thing that can be executed; the json is
          parsed and validated; the pdf is prose and is never read as
          configuration. A single "attachments" picker would lose that. */}
      <div className="models-upload-files">
        <FilePicker
          label={t("models.modelFile")}
          hint={t("models.fileHint")}
          accept={ACCEPTED.model}
          file={modelFile}
          onPick={(file) => choose(file, ACCEPTED.model, setModelFile)}
        />
        <FilePicker
          label={t("models.metadataFile")}
          hint={t("models.metadataHint")}
          accept={ACCEPTED.metadata}
          file={metadataFile}
          onPick={(file) => choose(file, ACCEPTED.metadata, setMetadataFile)}
        />
        <FilePicker
          label={t("models.documentFile")}
          hint={t("models.documentHint")}
          accept={ACCEPTED.document}
          file={documentFile}
          onPick={(file) => choose(file, ACCEPTED.document, setDocumentFile)}
        />
      </div>

      {refusal ? <div className="notice notice--warn">{refusal}</div> : null}

      <div className="models-upload-actions">
        <button
          type="button"
          className="primary"
          disabled={!ready || percent !== null}
          onClick={() => void submit()}
        >
          {percent === null ? t("models.upload") : t("models.uploading")}
        </button>
        {percent !== null ? (
          <>
            {/* A number as well as a bar: "84%" is what somebody reads
                out when asking whether it is stuck. */}
            <progress className="models-progress" max={100} value={percent} />
            <span className="muted small">{percent}%</span>
          </>
        ) : null}
      </div>
    </div>
  );
}

/** Change what is written about a model already on the shelf.
 *
 * **The .zip is not on the list, and the server is why.** Attaching a
 * `model` kind is refused outright — "the model file is set at upload
 * time; create a new version instead of replacing the bytes of an
 * existing one" — and that refusal is the same rule that keeps a
 * benchmarked model from being deleted. Results are filed against this
 * id; swapping the bytes underneath them turns a measurement into a
 * record of a file that no longer exists.
 *
 * So the panel says that out loud and hands over a button that opens the
 * upload form filled in, rather than offering a picker that would answer
 * with a 400 after the file had been chosen.
 */
function EditPanel({
  models,
  profiles,
  onChanged,
  onNewVersion,
}: {
  models: ModelSummary[];
  profiles: RobotProfile[];
  onChanged: (model: ModelSummary) => void;
  onNewVersion: (model: ModelSummary) => void;
}) {
  const { t } = useTranslation();
  const [chosenId, setChosenId] = useState("");
  const [name, setName] = useState("");
  const [version, setVersion] = useState("");
  const [description, setDescription] = useState("");
  const [robotProfileId, setRobotProfileId] = useState("");
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  const [refusal, setRefusal] = useState<string | null>(null);

  // Only a model this account owns can be changed; the server enforces
  // it, and a picker offering the rest would collect a form and answer
  // with a 403.
  const mine = models.filter((model) => model.is_owner);
  const chosen = mine.find((model) => model.id === chosenId) ?? null;

  useEffect(() => {
    if (!chosenId && mine.length > 0) setChosenId(mine[0].id);
  }, [mine, chosenId]);

  /* The fields follow the selection. Without this, switching models
     leaves the previous one's name in the box and the next save writes
     it onto the wrong record. */
  useEffect(() => {
    if (!chosen) return;
    setName(chosen.name);
    setVersion(chosen.version);
    setDescription(chosen.description);
    setRobotProfileId(chosen.robot_profile_id);
    setNote(null);
    setRefusal(null);
  }, [chosen?.id]);

  if (mine.length === 0) {
    return <p className="muted models-edit-empty">{t("models.edit.none")}</p>;
  }

  const save = async () => {
    if (!chosen) return;
    setBusy(true);
    setRefusal(null);
    try {
      onChanged(
        await updateModel(chosen.id, {
          name,
          version,
          description,
          robot_profile_id: robotProfileId,
        }),
      );
      setNote(t("models.edit.saved"));
    } catch (caught) {
      setRefusal(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setBusy(false);
    }
  };

  const replace = async (kind: "metadata" | "document", file: File | null) => {
    if (!chosen || !file) return;
    const expected = kind === "metadata" ? ACCEPTED.metadata : ACCEPTED.document;
    const actual = extensionOf(file.name);
    if (actual !== expected) {
      // Checked before sending for the same reason the upload form does
      // it: the server refuses too, and finding out afterwards costs the
      // transfer to deliver the answer.
      setRefusal(t("models.wrongExtension", { expected, actual: actual || "—" }));
      return;
    }
    setBusy(true);
    setRefusal(null);
    try {
      await attachDocument(chosen.id, kind, file);
      setNote(t("models.edit.saved"));
    } catch (caught) {
      setRefusal(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="models-edit">
      <label className="field">
        <span>{t("models.edit.pick")}</span>
        <select value={chosenId} onChange={(event) => setChosenId(event.target.value)}>
          {mine.map((model) => (
            <option key={model.id} value={model.id}>
              {model.name} · v{model.version}
            </option>
          ))}
        </select>
      </label>

      {chosen ? (
        <>
          <div className="models-upload-grid">
            <label className="field">
              <span>{t("models.name")}</span>
              <input value={name} onChange={(event) => setName(event.target.value)} />
            </label>
            <label className="field">
              <span>{t("models.version")}</span>
              <input value={version} onChange={(event) => setVersion(event.target.value)} />
            </label>
            <label className="field">
              <span>{t("models.robotProfile")}</span>
              <select
                value={robotProfileId}
                onChange={(event) => setRobotProfileId(event.target.value)}
              >
                {profiles.map((profile) => (
                  <option key={profile.id} value={profile.id}>
                    {profile.name} · {profile.lidar_beams} beams
                  </option>
                ))}
              </select>
            </label>
            <label className="field models-upload-wide">
              <span>{t("models.description")}</span>
              <input
                value={description}
                onChange={(event) => setDescription(event.target.value)}
              />
            </label>
          </div>

          <div className="models-upload-files">
            <FilePicker
              label={t("models.edit.replaceMetadata")}
              hint={t("models.metadataHint")}
              accept={ACCEPTED.metadata}
              file={null}
              onPick={(file) => void replace("metadata", file)}
            />
            <FilePicker
              label={t("models.edit.replaceDocument")}
              hint={t("models.documentHint")}
              accept={ACCEPTED.document}
              file={null}
              onPick={(file) => void replace("document", file)}
            />
            {/* No picker for the .zip. A control that collects a 200 MB
                file and then reports that this was never allowed is a
                worse answer than the sentence. */}
            <div className="field models-file models-file--fixed">
              <span>{t("models.edit.replaceFile")}</span>
              <p className="muted small">{t("models.edit.fileFixed")}</p>
              <button type="button" onClick={() => onNewVersion(chosen)}>
                {t("models.edit.newVersion")}
              </button>
            </div>
          </div>

          {refusal ? <div className="notice notice--warn">{refusal}</div> : null}
          {note && !refusal ? <p className="muted">{note}</p> : null}

          <div className="models-upload-actions">
            <button type="button" className="primary" disabled={busy} onClick={() => void save()}>
              {busy ? t("models.edit.saving") : t("models.edit.save")}
            </button>
          </div>
        </>
      ) : null}
    </div>
  );
}

function FilePicker({
  label,
  hint,
  accept,
  file,
  onPick,
}: {
  label: string;
  hint: string;
  accept: string;
  file: File | null;
  onPick: (file: File | null) => void;
}) {
  return (
    <label className="field models-file">
      <span>
        {label} <Hint text={hint} label={label} />
      </span>
      <input
        type="file"
        accept={accept}
        onChange={(event) => onPick(event.target.files?.[0] ?? null)}
      />
      {file ? <span className="muted small">{formatSize(file.size)}</span> : null}
    </label>
  );
}
