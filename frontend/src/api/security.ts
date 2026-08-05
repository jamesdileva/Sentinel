import { api } from "./client";

export interface SecurityFinding {
  id: string;
  project_id: string;
  tool: string;
  severity: "critical" | "high" | "medium" | "low" | "info";
  title: string;
  description: string | null;
  file_path: string | null;
  created_at: string;
}

export interface ScanJob {
  id: string;
  project_id: string;
  status: "queued" | "running" | "succeeded" | "failed";
  created_at: string;
}

export async function triggerScan(projectId: string): Promise<ScanJob> {
  const { data } = await api.post<ScanJob>("/v1/security/scan", {
    project_id: projectId,
  });
  return data;
}

export async function getFindings(projectId: string): Promise<SecurityFinding[]> {
  const { data } = await api.get<SecurityFinding[]>("/v1/security/findings", {
    params: { project_id: projectId },
  });
  return data;
}
