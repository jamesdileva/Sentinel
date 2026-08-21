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
  /** Discovered install/startup/build/test/deploy commands (ProjectRead.stack). */
  stack?: { commands: Record<string, string> } | null;
}

export interface ProjectFile {
  /** Mirrors ProjectFileRead — only the fields the API actually returns. */
  id: string;
  path: string;
  language: string | null;
  size_bytes: number | null;
  summary: string | null;
  created_at: string;
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

/* --- Observatory (Sprint 10.5) ------------------------------------------ */

export interface GalaxyNode {
  id: string;
  kind: "project" | "tech";
  label: string;
  detail: string | null;
  // v1.17.9.1: project framework for the focus panel (null for tech nodes).
  framework?: string | null;
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
  has_more: boolean;
}

export interface ArchitectureNode {
  name: string;
  path: string;
  kind: "dir" | "file";
  count: number;
  children: ArchitectureNode[];
}
