import { api } from "./client";

export interface RagResult {
  content: string;
  source: string;
  project_id: string;
  file_path: string | null;
  distance: number;
}

export interface RagSearchResponse {
  query: string;
  results: RagResult[];
}

export interface RagResponse {
  answer: string;
  sources: RagResult[];
  model: string;
  generated_at: string;
  confidence: number;
}

export interface RagJob {
  job_id: string;
  status: "queued" | "running" | "succeeded" | "failed";
}

export interface KnowledgeSummary {
  id: string;
  project_id: string;
  type: string;
  content: string;
  model: string | null;
  confidence: number | null;
  generated_at: string | null;
}

export interface ProjectIndexStatus {
  files: number;
  embedded: number;
}

export interface RagIndexStatus {
  project_id: string | null;
  projects: Record<string, ProjectIndexStatus>;
  files_total: number;
  files_embedded: number;
}

export async function ragSearch(
  query: string,
  projectId?: string,
  topK = 5,
): Promise<RagSearchResponse> {
  const { data } = await api.post<RagSearchResponse>("/v1/rag/search", {
    query,
    project_id: projectId ?? null,
    top_k: topK,
  });
  return data;
}

// Local LLM generation can take a while — use a generous per-request timeout.
export async function ragQuery(
  question: string,
  projectId?: string,
  topK = 5,
): Promise<RagResponse> {
  const { data } = await api.post<RagResponse>(
    "/v1/rag/query",
    { question, project_id: projectId ?? null, top_k: topK },
    { timeout: 120_000 },
  );
  return data;
}

export async function ragIndex(
  projectId: string,
  withSummary = false,
): Promise<RagJob> {
  const { data } = await api.post<RagJob>("/v1/rag/index", {
    project_id: projectId,
    with_summary: withSummary,
  });
  return data;
}

export async function listSummaries(
  projectId: string,
  type?: string,
): Promise<KnowledgeSummary[]> {
  const { data } = await api.get<KnowledgeSummary[]>(
    `/v1/projects/${projectId}/summaries`,
    { params: { type } },
  );
  return data;
}

export async function getIndexStatus(
  projectId?: string,
): Promise<RagIndexStatus> {
  const { data } = await api.get<RagIndexStatus>("/v1/rag/index/status", {
    params: projectId ? { project_id: projectId } : undefined,
  });
  return data;
}