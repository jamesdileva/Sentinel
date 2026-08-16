import { api } from "./client";

export type SessionStatus = "running" | "passed" | "failed" | "investigate";

export interface SessionCheckpoint {
  id: string;
  session_id: string;
  label: string;
  at: string;
}

export interface SessionScreenshot {
  id: string;
  session_id: string;
  checkpoint_id: string | null;
  path: string;
  captured_at: string;
}

export interface SessionRecord {
  id: string;
  project_id: string;
  project_name: string | null;
  title: string;
  expected_output: string | null;
  actual_outcome: string | null;
  status: SessionStatus;
  started_at: string;
  ended_at: string | null;
  log_slice: string | null;
  checkpoints: SessionCheckpoint[];
  screenshots: SessionScreenshot[];
}

export interface SessionExport {
  copied: string[];
  snippet: string;
}

export interface TriageSourceLine {
  line_number: number;
  text: string;
}

export interface TriageFrame {
  file: string;
  relative_path: string;
  line: number;
  function: string | null;
  source: TriageSourceLine[];
}

export interface TriageEvidence {
  status: string;
  actual_outcome: string | null;
  error_lines: string[];
  patterns: string[];
  frames: TriageFrame[];
  traceback_available: boolean;
  note: string | null;
}

export interface TriageRecord {
  id: string;
  session_id: string;
  evidence: TriageEvidence;
  summary: string | null;
  model: string | null;
  created_at: string;
}

export interface SessionCreate {
  project_id: string;
  title: string;
  expected_output?: string | null;
}

export function screenshotUrl(sessionId: string, filename: string): string {
  return `/api/v1/sessions/${sessionId}/screenshots/${filename}`;
}

export async function listSessions(
  projectId?: string,
  status?: SessionStatus,
): Promise<SessionRecord[]> {
  const { data } = await api.get<SessionRecord[]>("/v1/sessions", {
    params: { project_id: projectId, status },
  });
  return data;
}

export async function getSession(sessionId: string): Promise<SessionRecord> {
  const { data } = await api.get<SessionRecord>(`/v1/sessions/${sessionId}`);
  return data;
}

export async function startSession(
  body: SessionCreate,
): Promise<SessionRecord> {
  const { data } = await api.post<SessionRecord>("/v1/sessions", body);
  return data;
}

export async function updateSession(
  sessionId: string,
  patch: Partial<SessionCreate> & { status?: SessionStatus },
): Promise<SessionRecord> {
  const { data } = await api.patch<SessionRecord>(
    `/v1/sessions/${sessionId}`,
    patch,
  );
  return data;
}

export async function addCheckpoint(
  sessionId: string,
  label: string,
): Promise<SessionCheckpoint> {
  const { data } = await api.post<SessionCheckpoint>(
    `/v1/sessions/${sessionId}/checkpoints`,
    { label },
  );
  return data;
}

export async function endSession(
  sessionId: string,
  actualOutcome: string | null,
  status: Exclude<SessionStatus, "running">,
): Promise<SessionRecord> {
  const { data } = await api.post<SessionRecord>(
    `/v1/sessions/${sessionId}/end`,
    {
      actual_outcome: actualOutcome,
      status,
    },
  );
  return data;
}

export async function captureScreenshot(
  sessionId: string,
  checkpointId?: string,
): Promise<SessionScreenshot> {
  const { data } = await api.post<SessionScreenshot>(
    `/v1/sessions/${sessionId}/screenshots`,
    { checkpoint_id: checkpointId ?? null },
  );
  return data;
}

export async function exportScreenshot(
  sessionId: string,
  screenshotId: string,
): Promise<SessionExport> {
  const { data } = await api.post<SessionExport>(
    `/v1/sessions/${sessionId}/screenshots/${screenshotId}/export`,
  );
  return data;
}

export async function deleteSession(sessionId: string): Promise<void> {
  await api.delete(`/v1/sessions/${sessionId}`);
}

export async function triageSession(sessionId: string): Promise<TriageRecord> {
  const { data } = await api.post<TriageRecord>(
    `/v1/sessions/${sessionId}/triage`,
  );
  return data;
}

export async function summarizeSession(
  sessionId: string,
): Promise<TriageRecord> {
  const { data } = await api.post<TriageRecord>(
    `/v1/sessions/${sessionId}/summarize`,
  );
  return data;
}
