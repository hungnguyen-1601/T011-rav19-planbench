"use client";

/** The model registry, from the browser's side.
 *
 * The client sends a model **id** and never a path. It has no way to
 * name a location on the server, which is the point: the previous design
 * asked a user to type one.
 *
 * Upload goes through `XMLHttpRequest` rather than `fetch` for one
 * reason — progress. A 200 MB checkpoint on a slow connection with no
 * progress bar looks identical to a hung page, and `fetch` still cannot
 * report upload progress.
 */

import { API_BASE } from "./api";
import { authFetch, loadSession } from "./auth";

export type ModelStatus = "active" | "disabled";
export type ValidationStatus = "pending" | "structural" | "loaded" | "failed";
export type Compatibility = "compatible" | "warning" | "incompatible";

export interface ObservationSchema {
  type: string;
  shape: number[];
  lidar_beams: number;
  includes_goal_direction: boolean;
  includes_current_velocity: boolean;
}

export interface ActionSchema {
  type: string;
  shape: number[];
  fields: string[];
}

export interface ModelSummary {
  id: string;
  name: string;
  version: string;
  description: string;
  algorithm_type: string;
  framework: string;
  robot_profile_id: string;
  status: ModelStatus;
  validation_status: ValidationStatus;
  validation_message: string;
  file_size: number;
  checksum: string;
  training_environment: string;
  training_steps: number;
  observation_schema: ObservationSchema;
  action_schema: ActionSchema;
  created_at: string;
  is_owner: boolean;
}

export interface CompatibilityReport {
  status: Compatibility;
  model_id: string;
  robot_profile_id: string;
  errors: string[];
  warnings: string[];
  checked_at: string;
}

export interface ModelDetail {
  model: ModelSummary;
  compatibility: CompatibilityReport;
  used_by_benchmarks: string[];
  documents: { id: string; kind: string; filename: string; size: number }[];
}

export interface RobotProfile {
  id: string;
  name: string;
  version: string;
  description: string;
  radius: number;
  footprint: string;
  max_linear_velocity: number;
  max_angular_velocity: number;
  /** Null means the profile never declared it, which is not the same as
   *  zero: zero would be a robot that cannot change speed. A deployment
   *  needs both, so a form filling itself from a profile has to leave
   *  these to their author rather than substitute a number nobody
   *  checked. */
  max_linear_acceleration: number | null;
  max_angular_acceleration: number | null;
  lidar_beams: number;
  lidar_range: number;
  observation_type: string;
  action_type: string;
  created_by_user_id: string;
  created_at: string;
  updated_at: string;
}

export function listModels(usableOnly = false): Promise<ModelSummary[]> {
  return authFetch<ModelSummary[]>(`/models?usable_only=${usableOnly}`);
}

export function getModel(id: string): Promise<ModelDetail> {
  return authFetch<ModelDetail>(`/models/${id}`);
}

export function deleteModel(id: string): Promise<void> {
  return authFetch<void>(`/models/${id}`, { method: "DELETE" });
}

export function setModelStatus(id: string, status: ModelStatus): Promise<ModelSummary> {
  return authFetch<ModelSummary>(`/models/${id}`, {
    method: "PATCH",
    body: JSON.stringify({ status }),
  });
}

export function revalidateModel(id: string): Promise<ModelSummary> {
  return authFetch<ModelSummary>(`/models/${id}/validate`, { method: "POST" });
}

export function modelCompatibility(
  id: string,
  robotProfileId?: string,
): Promise<CompatibilityReport> {
  const query = robotProfileId ? `?robot_profile_id=${encodeURIComponent(robotProfileId)}` : "";
  return authFetch<CompatibilityReport>(`/models/${id}/compatibility${query}`);
}

export function listRobotProfiles(): Promise<RobotProfile[]> {
  return authFetch<RobotProfile[]>("/robot-profiles");
}

export interface UploadFields {
  name: string;
  version: string;
  description: string;
  framework: string;
  frameworkVersion: string;
  robotProfileId: string;
  trainingEnvironment: string;
  modelFile: File;
  metadataFile?: File | null;
  documentFile?: File | null;
}

/** The three kinds of file, and what each is for. */
export const ACCEPTED = {
  /** The only one that can be run as a policy. */
  model: ".zip",
  /** Structured description. Validated, never executed. */
  metadata: ".json",
  /** Prose for humans. Never parsed as configuration. */
  document: ".pdf",
} as const;

export function extensionOf(filename: string): string {
  const index = filename.lastIndexOf(".");
  return index < 0 ? "" : filename.slice(index).toLowerCase();
}

/** Bytes as something a person reads. */
export function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/**
 * Upload a model, reporting progress.
 *
 * Rejects with the server's message, not a status code: "this file is
 * not a zip archive" is what the user needs, and the API is written to
 * say exactly that.
 */
export function uploadModel(
  fields: UploadFields,
  onProgress: (percent: number) => void,
): Promise<ModelSummary> {
  const session = loadSession();
  const body = new FormData();
  body.append("name", fields.name);
  body.append("version", fields.version || "1");
  body.append("description", fields.description);
  body.append("framework", fields.framework);
  body.append("framework_version", fields.frameworkVersion);
  body.append("robot_profile_id", fields.robotProfileId);
  body.append("training_environment", fields.trainingEnvironment);
  body.append("model_file", fields.modelFile);
  if (fields.metadataFile) body.append("metadata_file", fields.metadataFile);
  if (fields.documentFile) body.append("document_file", fields.documentFile);

  return new Promise<ModelSummary>((resolve, reject) => {
    const request = new XMLHttpRequest();
    request.open("POST", `${API_BASE}/api/v1/models/upload`);
    if (session) request.setRequestHeader("Authorization", `Bearer ${session.token}`);

    request.upload.onprogress = (event) => {
      if (event.lengthComputable) onProgress(Math.round((event.loaded / event.total) * 100));
    };
    request.onload = () => {
      let body: unknown = null;
      try {
        body = JSON.parse(request.responseText);
      } catch {
        // A non-JSON body means something upstream failed; the status
        // below is then the only thing worth reporting.
      }
      if (request.status >= 200 && request.status < 300) {
        resolve(body as ModelSummary);
        return;
      }
      const message =
        (body as { error?: { message?: string } })?.error?.message ??
        `Upload failed (${request.status})`;
      reject(new Error(message));
    };
    request.onerror = () => reject(new Error("The upload could not reach the server."));
    request.onabort = () => reject(new Error("Upload cancelled."));
    request.send(body);
  });
}

/** Whether a model can be offered in a benchmark form. */
export function isUsable(model: ModelSummary): boolean {
  return (
    model.status === "active" &&
    (model.validation_status === "structural" || model.validation_status === "loaded")
  );
}
