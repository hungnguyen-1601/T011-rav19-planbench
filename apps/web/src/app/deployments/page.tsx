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

import { useCallback, useEffect, useState } from "react";
import { EmptyState } from "@/components/EmptyState";
import { useSession } from "@/lib/auth";
import { useTranslation } from "@/lib/i18n";
import {
  createTaskProfile,
  listTaskProfiles,
  type TaskProfileSummary,
} from "@/lib/decisions";

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

export default function DeploymentsPage() {
  const { t } = useTranslation();
  const session = useSession();
  const [profiles, setProfiles] = useState<TaskProfileSummary[]>([]);
  const [draft, setDraft] = useState("");
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

  const file = async () => {
    setBusy(true);
    setError(null);
    setFiled(null);
    try {
      // Parsed here only to turn YAML into the JSON body the API takes.
      // Validation is the server's — `TaskProfile` is the single
      // definition of HĐ-2, and a second opinion in the browser would be
      // free to disagree with the one that decides.
      const { parse } = await import("yaml");
      const created = await createTaskProfile(parse(draft));
      setFiled(created.id);
      setDraft("");
      await refresh();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setBusy(false);
    }
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
                </tr>
              </thead>
              <tbody>
                {profiles.map((profile) => (
                  <DeploymentRow key={profile.id} profile={profile} />
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
            <p className="muted">{t("deployments.file.note")}</p>
            <textarea
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              placeholder={t("deployments.file.placeholder")}
              rows={14}
              spellCheck={false}
              disabled={busy}
              style={{ width: "100%", fontFamily: "monospace" }}
            />
            <div className="row" style={{ marginTop: 12, alignItems: "center", gap: 12 }}>
              <button
                type="button"
                className="primary"
                disabled={busy || !draft.trim()}
                onClick={() => void file()}
              >
                {t("deployments.file.submit")}
              </button>
              <span className="muted">{t("deployments.file.idRule")}</span>
            </div>
          </>
        )}
      </div>
    </section>
  );
}

function DeploymentRow({ profile }: { profile: TaskProfileSummary }) {
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
    </tr>
  );
}
