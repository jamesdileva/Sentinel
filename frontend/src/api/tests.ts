import { api } from "./client";

export interface TestResult {
  id: string;
  project_id: string;
  run_at: string;
  passed: number;
  failed: number;
  errors: number;
  skipped: number;
  duration_seconds: number | null;
  framework: string | null;
  summary: string | null;
}

export interface TestRunJob {
  job_id: string;
  status: "queued" | "running" | "succeeded" | "failed";
}

export async function triggerTestRun(projectId: string): Promise<TestRunJob> {
  const { data } = await api.post<TestRunJob>("/v1/tests/run", null, {
    params: { project_id: projectId },
  });
  return data;
}

export async function getTestResults(projectId: string): Promise<TestResult[]> {
  const { data } = await api.get<TestResult[]>("/v1/tests/results", {
    params: { project_id: projectId },
  });
  return data;
}