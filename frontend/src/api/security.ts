import { api } from "./client";

export type FindingSeverity = "critical" | "high" | "medium" | "low" | "info";
export type FindingType = "vulnerability" | "secret" | "static_analysis";

export interface SecurityFinding {
  id: string;
  project_id: string;
  type: FindingType;
  severity: FindingSeverity;
  title: string;
  description: string | null;
  ai_explanation: string | null;
  file_path: string | null;
  line_number: number | null;
  cve_id: string | null;
  remediation: string | null;
  resolved: boolean;
  detected_at: string;
}

export interface ScanJob {
  job_id: string;
  status: "queued" | "running" | "succeeded" | "failed";
}

export async function triggerScan(projectId: string): Promise<ScanJob> {
  const { data } = await api.post<ScanJob>("/v1/security/scan", null, {
    params: { project_id: projectId },
  });
  return data;
}

export async function triggerScanAll(): Promise<ScanJob> {
  const { data } = await api.post<ScanJob>("/v1/security/scan-all");
  return data;
}

export async function getFindings(projectId: string): Promise<SecurityFinding[]> {
  const { data } = await api.get<SecurityFinding[]>("/v1/security/findings", {
    params: { project_id: projectId },
  });
  return data;
}