import { api } from "./client";

export interface BuildJob {
  id: string;
  project_id: string;
  status: "queued" | "running" | "succeeded" | "failed" | "skipped";
  success: boolean | null;
  exit_code: number | null;
  started_at: string | null;
  completed_at: string | null;
}

export interface BuildLog {
  id: string;
  project_id: string;
  started_at: string;
  completed_at: string | null;
  exit_code: number | null;
  success: boolean | null;
  stdout: string | null;
  stderr: string | null;
  commands: Record<string, string> | null;
}

export async function triggerBuild(projectId: string): Promise<BuildJob> {
  const { data } = await api.post<BuildJob>("/v1/builds/run", {
    project_id: projectId,
  });
  return data;
}

export async function getBuildStatus(jobId: string): Promise<BuildJob> {
  const { data } = await api.get<BuildJob>(`/v1/builds/status/${jobId}`);
  return data;
}

export async function getBuildHistory(projectId: string): Promise<BuildLog[]> {
  const { data } = await api.get<BuildLog[]>("/v1/builds/history", {
    params: { project_id: projectId },
  });
  return data;
}