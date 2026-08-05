import { api } from "./client";

import type { Project } from "../types";

export interface PortfolioScore {
  project_id: string;
  health_score: number;
  build: string;
  tests: string;
  security: string;
  docs_pct: number;
}

export interface PortfolioCandidate extends PortfolioScore {
  project: Project;
}

export interface FeatureMatrixRow {
  project_id: string;
  name: string;
  build: boolean;
  tests: boolean;
  docs: boolean;
  security: boolean;
}

export async function getScores(): Promise<PortfolioScore[]> {
  const { data } = await api.get<PortfolioScore[]>("/v1/portfolio/scores");
  return data;
}

export async function getBestCandidates(): Promise<PortfolioCandidate[]> {
  const { data } = await api.get<PortfolioCandidate[]>(
    "/v1/portfolio/best-candidates",
  );
  return data;
}

export async function getFeatureMatrix(): Promise<FeatureMatrixRow[]> {
  const { data } = await api.get<FeatureMatrixRow[]>("/v1/portfolio/feature-matrix");
  return data;
}
