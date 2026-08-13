"use client";

/** Deployments — the question a selection run answers.
 *
 * A task profile is the map, the mission, the robot, the declared sensor
 * noise and the six thresholds, together. It is where the noise lives
 * and it is *not* a per-run option, which is the part that surprises
 * people: changing sigma changes the world, and `episode_context_id`
 * does not hash the amplitudes (HĐ-3.1). Two runs at the same seeds
 * under different noise would have identical context ids and be two
 * different experiments — so a changed deployment needs a new id, and
 * the server refuses the alternative.
 *
 * Filing is by pasting the YAML rather than by a form with thirty
 * fields. The profile is a contract document under HĐ-2 with a validator
 * that already refuses the interesting mistakes — a heading requirement
 * the platform cannot evaluate, traffic that shifts by less than one
 * period, a RAM budget that does not add up. A form would either
 * re-implement that validation or let the user build something the
 * server rejects field by field.
 */

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { DeploymentForm } from "@/components/DeploymentForm";
import { EmptyState } from "@/components/EmptyState";
import { fieldErrorsOf, useSession } from "@/lib/auth";
import {
  createTaskProfile,
  deleteTaskProfile,
  listTaskProfiles,
  type DeletionBlocked,
  type TaskProfileSummary,
} from "@/lib/decisions";
import type { ProfileDraft } from "@/lib/deployments";
import { useTranslation } from "@/lib/i18n";

interface Constraints {
  success_rate_min?: number;
  collision_probability_max?: number;
  n_min_evaluation_episodes?: number;
  [field: string]: unknown;
}

interface Environment {
  map?: string;
  sensor_noise?: { lidar_range_sigma_m?: number; wheel_slip_fraction?: number };
  [field: string]: unknown;
}

function constraintsOf(profile: TaskProfileSummary): Constraints {
  return (profile.profile?.constraints ?? {}) as Constraints;
}

function environmentOf(profile: TaskProfileSummary): Environment {
  return (profile.profile?.environment ?? {}) as Environment;
}

/** Fill in fields, or paste the document. Both build one profile. */
type Mode = "form" | "yaml";

export default function DeploymentsPage() {
  const { t } = useTranslation();
  const session = useSession();
  const [profiles, setProfiles] = useState<TaskProfileSummary[]>([]);
  const [mode, setMode] = useState<Mode>("form");
  const [draft, setDraft] = useState("");
  const [formDraft, setFormDraft] = useState<ProfileDraft | null>(null);
  const [fieldErrors, setFieldErrors] = useState<{ path: string; message: string }[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [filed, setFiled] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      setProfiles(await listTaskProfiles());
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

  /** File a profile. **One path for both tabs**, because a profile filed
   *  from the form and one pasted as YAML have to be the same act — the
   *  moment they are two, they are free to send two different shapes.
   *
   *  Refusals come back whole: the sentence for the reader and, since
   *  the server started addressing them, one entry per offending field
   *  for the form to outline. Nothing here decides anything. */
  const file = async (profile: ProfileDraft) => {
    setBusy(true);
    setError(null);
    setFiled(null);
    setFieldErrors([]);
    try {
      const created = await createTaskProfile(profile);
      setFiled(created.id);
      setDraft("");
      setFormDraft(null);
      await refresh();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
      setFieldErrors(fieldErrorsOf(caught));
    } finally {
      setBusy(false);
    }
  };

  const fileYaml = async () => {
    // Parsed here only to turn YAML into the JSON body the API takes.
    // Validation is the server's — `TaskProfile` is the single
    // definition of HĐ-2, and a second opinion in the browser would be
    // free to disagree with the one that decides.
    try {
      const { parse } = await import("yaml");
      await file(parse(draft) as ProfileDraft);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
    }
  };

  /** Move between the two tabs without losing what is already typed.
   *
   * Form → YAML **carries the draft over**, so the reader can see exactly
   * what the form built and hand-edit a block the form does not cover.
   *
   * YAML → form **does not carry anything back**, and says so. Loading a
   * pasted document into a form that cannot express `dynamic_obstacles`
   * would silently swallow that block, and the author would file a
   * deployment missing the traffic they had just written.
   */
  const switchTo = (next: Mode) => {
    if (next === "yaml" && formDraft) {
      void (async () => {
        const { stringify } = await import("yaml");
        setDraft(stringify(formDraft));
        setMode("yaml");
      })();
      return;
    }
    setMode(next);
  };

  return (
    <section>
      <div className="page-head">
        <h1>{t("deployments.title")}</h1>
        <p className="muted">{t("deployments.subtitle")}</p>
      </div>

      {error ? <div className="error-box">{error}</div> : null}
      {filed ? (
        <div className="notice">{t("deployments.filed", { id: filed })}</div>
      ) : null}

      {loading ? (
        <p className="muted">{t("common.loading")}</p>
      ) : profiles.length === 0 ? (
        <EmptyState
          icon="map"
          title={t("deployments.empty.title")}
          body={t("deployments.empty.body")}
        />
      ) : (
        <div className="panel">
          <div className="table-scroll wide">
            <table>
              <thead>
                <tr>
                  <th>{t("deployments.column.id")}</th>
                  <th>{t("deployments.column.map")}</th>
                  <th>{t("deployments.column.noise")}</th>
                  <th>{t("deployments.column.successMin")}</th>
                  <th>{t("deployments.column.risk")}</th>
                  <th>{t("deployments.column.nMin")}</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {profiles.map((profile) => (
                  <DeploymentRow key={profile.id} profile={profile} onDeleted={refresh} />
                ))}
              </tbody>
            </table>
          </div>
          <p className="muted" style={{ marginTop: 12 }}>
            {t("deployments.noiseNote")}
          </p>
        </div>
      )}

      <div className="panel">
        <div className="panel-head">
          <h3>{t("deployments.file.title")}</h3>
        </div>
        {!session ? (
          <p className="muted">{t("deployments.file.signedOut")}</p>
        ) : (
          <>
            {/* Two ways in, one way out: both tabs build the same
                document and both POST it to the same endpoint. The form
                is the default because thirty labelled boxes are easier
                to start from than a blank textarea; the YAML tab stays
                because it is the only way to write the blocks the form
                does not cover yet — traffic, most of all. */}
            <div className="toolbar">
              {(["form", "yaml"] as Mode[]).map((option) => (
                <button
                  key={option}
                  type="button"
                  disabled={busy}
                  className={mode === option ? "active" : undefined}
                  aria-pressed={mode === option}
                  onClick={() => switchTo(option)}
                >
                  {t(`deployments.mode.${option}`)}
                </button>
              ))}
              <span className="muted">{t("deployments.mode.note")}</span>
            </div>

            {mode === "form" ? (
              <DeploymentForm
                draft={formDraft}
                onDraftChange={setFormDraft}
                onSubmit={file}
                busy={busy}
                fieldErrors={fieldErrors}
              />
            ) : (
              <>
                <p className="muted">{t("deployments.file.note")}</p>
                <textarea
                  value={draft}
                  onChange={(event) => setDraft(event.target.value)}
                  placeholder={t("deployments.file.placeholder")}
                  rows={18}
                  spellCheck={false}
                  disabled={busy}
                  style={{ width: "100%", fontFamily: "monospace" }}
                />
                <div className="row" style={{ marginTop: 12, alignItems: "center", gap: 12 }}>
                  <button
                    type="button"
                    className="primary"
                    disabled={busy || !draft.trim()}
                    onClick={() => void fileYaml()}
                  >
                    {t("deployments.file.submit")}
                  </button>
                  <span className="muted">{t("deployments.file.idRule")}</span>
                </div>
              </>
            )}
          </>
        )}
      </div>
    </section>
  );
}

function DeploymentRow({
  profile,
  onDeleted,
}: {
  profile: TaskProfileSummary;
  onDeleted: () => void;
}) {
  const { t } = useTranslation();
  const constraints = constraintsOf(profile);
  const noise = environmentOf(profile).sensor_noise;
  // Absent and zero are different claims. A profile with no
  // `sensor_noise` block was measured in a world with no noise at all,
  // and saying "0.00 m" for it would read as a measurement somebody
  // made rather than a block nobody wrote.
  const declared = noise !== undefined && noise !== null;

  return (
    <tr>
      <td>
        <strong>{profile.id}</strong>
      </td>
      <td className="muted">{environmentOf(profile).map ?? "—"}</td>
      <td>
        {declared ? (
          <span title={JSON.stringify(noise)}>
            σ {noise?.lidar_range_sigma_m ?? 0} m ·{" "}
            {((noise?.wheel_slip_fraction ?? 0) * 100).toFixed(1)}%
          </span>
        ) : (
          <span className="badge warn" title={t("deployments.noiseUndeclared")}>
            {t("deployments.noNoise")}
          </span>
        )}
      </td>
      <td>
        {constraints.success_rate_min !== undefined
          ? `${(constraints.success_rate_min * 100).toFixed(0)}%`
          : "—"}
      </td>
      <td>
        {constraints.collision_probability_max !== undefined
          ? `${(constraints.collision_probability_max * 100).toFixed(0)}%`
          : "—"}
      </td>
      <td title={t("deployments.nMinNote")}>
        {constraints.n_min_evaluation_episodes ?? "—"}
      </td>
      <td>
        <DeleteDeployment id={profile.id} onDeleted={onDeleted} />
      </td>
    </tr>
  );
}

/** Delete a deployment — one click, or two when something was measured.
 *
 * **The first attempt always asks the server**, even for a deployment
 * that looks untouched on screen. Whether anything was measured is a
 * fact about the run store, and a page that decided it from what it had
 * loaded would be a second answer free to disagree with the one that
 * actually governs the delete — including in the window between the list
 * being fetched and the button being pressed.
 *
 * So: try; if the server refuses, it hands back the counts, and those
 * counts are what the dialog says. "Delete 7 runs, 2 of them approved?"
 * is a question somebody can answer. "Are you sure?" is not.
 */
function DeleteDeployment({ id, onDeleted }: { id: string; onDeleted: () => void }) {
  const { t } = useTranslation();
  const [busy, setBusy] = useState(false);
  const [blocked, setBlocked] = useState<DeletionBlocked | null>(null);
  const [failed, setFailed] = useState<string | null>(null);

  const attempt = async (deleteRuns: boolean) => {
    setBusy(true);
    setFailed(null);
    try {
      const refusal = await deleteTaskProfile(id, { deleteRuns });
      if (refusal) {
        setBlocked(refusal);
        return;
      }
      setBlocked(null);
      onDeleted();
    } catch (caught) {
      setFailed(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setBusy(false);
    }
  };

  if (blocked) {
    /* Two refusals that look alike and are not. Runs pose a question a
       confirmation answers. An approved run does not: the approval and
       the record of who made it are what HĐ-14 exists to keep, so the way
       through is to withdraw it on the run — pressing harder here must
       not be offered at all, because a dialog whose confirm button
       destroys an audit trail is a speed bump, not a safeguard. */
    const permanent = (blocked.approved_ids?.length ?? 0) > 0;
    return (
      <div className="notice warn">
        <p>
          {permanent
            ? t("deployments.delete.approvedBlocked", { approved: String(blocked.approved) })
            : t("deployments.delete.blocked", {
                runs: String(blocked.runs),
                approved: String(blocked.approved),
              })}
        </p>
        <div className="row" style={{ gap: 8 }}>
          {permanent ? (
            <Link href={`/decisions?profile=${encodeURIComponent(id)}`}>
              {t("deployments.delete.openRuns")}
            </Link>
          ) : (
            <button type="button" disabled={busy} onClick={() => void attempt(true)}>
              {t("deployments.delete.confirm", { runs: String(blocked.runs) })}
            </button>
          )}
          <button type="button" className="primary" onClick={() => setBlocked(null)}>
            {t("common.cancel")}
          </button>
        </div>
        {failed ? <div className="error-box">{failed}</div> : null}
      </div>
    );
  }

  return (
    <>
      <button type="button" disabled={busy} onClick={() => void attempt(false)}>
        {busy ? t("deployments.delete.busy") : t("deployments.delete.action")}
      </button>
      {failed ? <span className="error-text">{failed}</span> : null}
    </>
  );
}
