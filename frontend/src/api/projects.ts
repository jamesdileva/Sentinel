import { api } from "./client";

import type { Project, ProjectFile } from "../types";

export interface ProjectListResponse {
  projects: Project[];
  total: number;
}

export async function listProjects(): Promise<ProjectListResponse> {
  const { data } = await api.get<ProjectListResponse>("/v1/projects/");
  return data;
}

export async function getProject(projectId: string): Promise<Project> {
  const { data } = await api.get<Project>(`/v1/projects/${projectId}`);
  return data;
}

export async function getProjectFiles(projectId: string): Promise<ProjectFile[]> {
  const { data } = await api.get<ProjectFile[]>(
    `/v1/projects/${projectId}/files`,
  );
  return data;
}
