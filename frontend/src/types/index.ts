/** Shared Sentinel types — mirror backend/app/db/models.py and schemas/. */

export interface Project {
  id: string;
  name: string;
  path: string;
  language: string;
  framework: string | null;
  status: "active" | "inactive" | "error";
  health_score: number | null;
  last_indexed: string | null;
  last_scanned: string | null;
  created_at: string;
  updated_at: string;
}

export interface ProjectFile {
  id: string;
  project_id: string;
  path: string;
  absolute_path: string;
  language: string | null;
  size_bytes: number | null;
  summary: string | null;
  embedding_id: string | null;
}

export interface Dependency {
  id: string;
  project_id: string;
  name: string;
  version: string | null;
  latest_version: string | null;
  type: "production" | "dev" | string;
  vulnerable: boolean;
  severity: "critical" | "high" | "medium" | "low" | "info" | null;
}

export interface DatabaseHealth {
  reachable: boolean;
  path: string;
}

export interface HealthResponse {
  status: string;
  app: string;
  version: string;
  database: DatabaseHealth;
}

export type ProjectStatus = Project["status"];
export type DependencyType = Dependency["type"];
