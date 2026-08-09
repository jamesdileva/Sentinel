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
