"use client";

/** Upload a trained PPO model.
 *
 * The three file inputs are deliberately distinct, because conflating
 * them is the misunderstanding this whole feature exists to prevent: the
 * `.zip` is the model and is the only thing that can run; the `.json`
 * describes it; the `.pdf` is prose. Each input says which it is, what
 * it is for, and refuses the wrong extension before a byte is sent.
 */

import { useRef, useState } from "react";

import { Icon } from "./Icon";
import { ErrorMessage } from "@/components/ErrorMessage";
import { useTranslation } from "@/lib/i18n";
import {
  ACCEPTED,
  extensionOf,
  formatSize,
  uploadModel,
  type ModelSummary,
  type RobotProfile,
} from "@/lib/models";

/** Matches PLANBENCH_MAX_MODEL_UPLOAD_MB / _DOCUMENT_ default. Checked
 *  here so a 300 MB file fails in a second rather than after a slow
 *  upload; the server enforces the real limit regardless. */
const MAX_MODEL_MB = 200;
const MAX_DOCUMENT_MB = 20;

interface FileSlot {
  file: File | null;
  error: string | null;
}

const EMPTY: FileSlot = { file: null, error: null };

export function ModelUpload({
  profiles,
  onUploaded,
  onCancel,
}: {
  profiles: RobotProfile[];
  onUploaded: (model: ModelSummary) => void;
  onCancel: () => void;
}) {
  const { t } = useTranslation();
  const [name, setName] = useState("");
  const [version, setVersion] = useState("1");
  const [description, setDescription] = useState("");
  const [framework] = useState("stable-baselines3");
  const [frameworkVersion, setFrameworkVersion] = useState("");
  const [profileId, setProfileId] = useState(profiles[0]?.id ?? "");
  const [environment, setEnvironment] = useState("");

  const [model, setModel] = useState<FileSlot>(EMPTY);
  const [metadata, setMetadata] = useState<FileSlot>(EMPTY);
  const [document, setDocument] = useState<FileSlot>(EMPTY);

  const [progress, setProgress] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const dialog = useRef<HTMLDivElement>(null);

  /** Check extension and size before anything leaves the browser. */
  const pick = (
    expected: string,
    limitMb: number,
    set: (slot: FileSlot) => void,
  ): ((event: React.ChangeEvent<HTMLInputElement>) => void) => {
    return (event) => {
      const file = event.target.files?.[0] ?? null;
      if (!file) {
        set(EMPTY);
        return;
      }
      const actual = extensionOf(file.name);
      if (actual !== expected) {
        set({ file: null, error: t("models.wrongExtension", { expected, actual: actual || "?" }) });
        return;
      }
      if (file.size > limitMb * 1024 * 1024) {
        set({
          file: null,
          error: t("models.tooLarge", { size: formatSize(file.size), limit: `${limitMb} MB` }),
        });
        return;
      }
      set({ file, error: null });
    };
  };

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!model.file) return;
    setProgress(0);
    setError(null);
    try {
      const created = await uploadModel(
        {
          name,
          version,
          description,
          framework,
          frameworkVersion,
          robotProfileId: profileId,
          trainingEnvironment: environment,
          modelFile: model.file,
          metadataFile: metadata.file,
          documentFile: document.file,
        },
        setProgress,
      );
      onUploaded(created);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setProgress(null);
    }
  };

  const busy = progress !== null;
  const ready = Boolean(name.trim() && profileId && model.file) && !busy;

  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true" aria-label={t("models.upload")}>
      <div className="modal" ref={dialog} style={{ maxWidth: 560 }}>
        <h3 style={{ marginTop: 0 }}>{t("models.upload")}</h3>
        {error ? <ErrorMessage error={error} /> : null}

        <form onSubmit={submit} style={{ display: "grid", gap: 12 }}>
          <div className="row" style={{ gap: 12 }}>
            <label className="field" style={{ flex: 2, minWidth: 180 }}>
              {t("models.name")}
              <input value={name} onChange={(e) => setName(e.target.value)} required autoFocus />
            </label>
            <label className="field" style={{ flex: 1, minWidth: 90 }}>
              {t("models.version")}
              <input value={version} onChange={(e) => setVersion(e.target.value)} />
            </label>
          </div>

          <label className="field">
            {t("models.description")}
            <input value={description} onChange={(e) => setDescription(e.target.value)} />
          </label>

          <div className="row" style={{ gap: 12 }}>
            <label className="field" style={{ flex: 1, minWidth: 160 }}>
              {t("models.robotProfile")}
              <select value={profileId} onChange={(e) => setProfileId(e.target.value)} required>
                {profiles.map((profile) => (
                  <option key={profile.id} value={profile.id}>
                    {profile.name} v{profile.version} · {profile.lidar_beams} beams
                  </option>
                ))}
              </select>
            </label>
            <label className="field" style={{ flex: 1, minWidth: 140 }}>
              {t("models.trainingEnvironment")}
              <input value={environment} onChange={(e) => setEnvironment(e.target.value)} />
            </label>
            <label className="field" style={{ flex: 1, minWidth: 120 }}>
              {t("models.frameworkVersion")}
              <input
                value={frameworkVersion}
                onChange={(e) => setFrameworkVersion(e.target.value)}
                placeholder="2.x"
              />
            </label>
          </div>

          <FileField
            label={t("models.modelFile")}
            hint={t("models.fileHint")}
            accept={ACCEPTED.model}
            slot={model}
            required
            onChange={pick(ACCEPTED.model, MAX_MODEL_MB, setModel)}
          />
          <FileField
            label={t("models.metadataFile")}
            hint={t("models.metadataHint")}
            accept={ACCEPTED.metadata}
            slot={metadata}
            onChange={pick(ACCEPTED.metadata, MAX_DOCUMENT_MB, setMetadata)}
          />
          <FileField
            label={t("models.documentFile")}
            hint={t("models.documentHint")}
            accept={ACCEPTED.document}
            slot={document}
            onChange={pick(ACCEPTED.document, MAX_DOCUMENT_MB, setDocument)}
          />

          {busy ? (
            <div>
              <div
                className="progress-track"
                role="progressbar"
                aria-label={t("models.uploading")}
                aria-valuenow={progress ?? 0}
                aria-valuemin={0}
                aria-valuemax={100}
              >
                <div className="progress-fill progress-active" style={{ width: `${progress}%` }} />
              </div>
              <span className="muted" style={{ fontSize: 12 }}>
                {t("models.uploading")} {progress}%
              </span>
            </div>
          ) : null}

          <div style={{ display: "flex", gap: 8 }}>
            <button
              className="primary"
              type="submit"
              disabled={!ready}
              title={
                !name.trim()
                  ? t("disabled.noName")
                  : !model.file
                    ? t("models.fileHint")
                    : busy
                      ? t("disabled.busy")
                      : undefined
              }
            >
              {busy ? t("models.uploading") : t("models.upload")}
            </button>
            <button
              type="button"
              onClick={onCancel}
              disabled={busy}
              title={busy ? t("disabled.busy") : undefined}
            >
              {t("common.cancel")}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function FileField({
  label,
  hint,
  accept,
  slot,
  required = false,
  onChange,
}: {
  label: string;
  hint: string;
  accept: string;
  slot: FileSlot;
  required?: boolean;
  onChange: (event: React.ChangeEvent<HTMLInputElement>) => void;
}) {
  return (
    <label className="field">
      {label}
      <input type="file" accept={accept} onChange={onChange} required={required} />
      {slot.error ? (
        <span className="badge err" style={{ marginTop: 4 }}>
          {slot.error}
        </span>
      ) : slot.file ? (
        <span className="muted" style={{ fontSize: 11, marginTop: 4 }}>
          <Icon name="check" size={12} /> {slot.file.name} · {formatSize(slot.file.size)}
        </span>
      ) : (
        <span className="muted" style={{ fontSize: 11, marginTop: 4 }}>
          {hint}
        </span>
      )}
    </label>
  );
}
