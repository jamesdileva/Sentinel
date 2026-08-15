import { api } from "./client";

export interface TesterDescriptor {
  name: string;
  description: string | null;
  kind: "custom" | "default-smoke";
}

export interface TesterJob {
  job_id: string;
  status: "queued" | "running" | "succeeded" | "failed";
}

export async function getTester(projectId: string): Promise<TesterDescriptor> {
  const { data } = await api.get<TesterDescriptor>(`/v1/testers/${projectId}`);
  return data;
}

export async function runTester(projectId: string): Promise<TesterJob> {
  const { data } = await api.post<TesterJob>("/v1/testers/run", {
    project_id: projectId,
  });
  return data;
}
