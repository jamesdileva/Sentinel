import { api } from "./client";

export interface BuildJob {
  id: string;
  project_id: string;
  status: "queued" | "running" | "succeeded" | "failed";
  exit_code: number | null;
  created_at: string;
}

export interface BuildLog {
  id: string;
  project_id: string;
  exit_code: number | null;
  output: string;
  created_at: string;
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
