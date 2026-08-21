import { api } from "./client";

export interface OllamaQueryRecord {
  model: string;
  prompt_chars: number;
  response_chars: number;
  eval_count: number;
  eval_duration_ns: number;
  total_duration_ns: number;
  tokens_per_second: number | null;
  latency_ms: number;
  created_at: string;
}

export interface OllamaStatus {
  available: boolean;
  host: string;
  model_default: string;
  models: string[];
  recent: OllamaQueryRecord[];
}

export interface SystemStartupState {
  name: string;
  ok: boolean;
  detail: string;
}

export interface SystemOverview {
  generated_at: string;
  startup: { states: SystemStartupState[] };
  ollama: OllamaStatus;
}

export interface SyncRun {
  status: "success" | "error" | "skipped";
  ran_at: string | null;
  cloned: string[];
  pulled: string[];
  failed: Record<string, string>;
  indexed: number;
  knowledge_queued: number;
  detail: string | null;
}

export interface SyncStatus {
  configured: boolean;
  last_run: SyncRun | null;
  interval_minutes: number;
}

export async function getSystemOverview(): Promise<SystemOverview> {
  const { data } = await api.get<SystemOverview>("/v1/system/overview");
  return data;
}

export async function getSyncStatus(): Promise<SyncStatus> {
  const { data } = await api.get<SyncStatus>("/v1/system/sync");
  return data;
}

export interface ActivityEvent {
  // Live WS frames have no id (only persisted history rows do) — audit2 F5.
  id?: string | null;
  kind: string;
  message: string;
  detail: string | null;
  /** Free-form event payload; null on live WS frames without data. */
  data: Record<string, unknown> | null;
  created_at: string;
}

export interface ActivityResponse {
  events: ActivityEvent[];
}

/**
 * Latest persisted activity, newest first. The backend wraps rows in an
 * `events` key (v1.17.1 fixed the shape mismatch that made the dashboard
 * history silently empty).
 */
export async function getActivity(limit = 100): Promise<ActivityEvent[]> {
  const { data } = await api.get<ActivityResponse>("/v1/system/activity", {
    params: { limit },
  });
  return data.events ?? [];
}

/**
 * Queue a repo sync now (header "Sync now" button, v1.17.1). Rejected with
 * 409 when SENTINEL_GITHUB_TOKEN is not configured.
 */
export async function postSyncNow(): Promise<{ job_id: string; status: string }> {
  const { data } = await api.post<{ job_id: string; status: string }>(
    "/v1/system/sync",
  );
  return data;
}
