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

/* --- Observatory (Sprint 10.5) ------------------------------------------ */

export interface GalaxyNode {
  id: string;
  kind: "project" | "tech";
  label: string;
  detail: string | null;
}

export interface GalaxyLink {
  source: string;
  target: string;
  tech: string;
}

export interface GalaxyGraph {
  nodes: GalaxyNode[];
  links: GalaxyLink[];
}

export interface TimelineEvent {
  at: string;
  kind: "project-created" | "commit" | "build" | "test" | "finding";
  project_id: string;
  project_name: string;
  message: string;
}

export interface Timeline {
  events: TimelineEvent[];
}

export interface ArchitectureNode {
  name: string;
  path: string;
  kind: "dir" | "file";
  count: number;
  children: ArchitectureNode[];
}
