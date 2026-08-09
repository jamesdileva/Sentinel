import { api } from "./client";

export type PassStatus = "passing" | "failing" | "pending";
export type SecurityStatus = "clean" | "findings" | "pending";

export interface PortfolioScore {
  id: string;
  project_id: string;
  build_status: PassStatus;
  test_status: PassStatus;
  documentation_pct: number;
  security_status: SecurityStatus;
  screenshots_available: boolean;
  portfolio_score: number;
  updated_at: string;
}

export interface PortfolioCandidate {
  project_id: string;
  project_name: string;
  score: number;
  missing: string[];
}

export interface FeatureMatrix {
  projects: string[];
  features: string[];
  matrix: string[][];
}

export interface PortfolioSummary {
  projects: number;
  buildable: number;
  open_findings: number;
  avg_health: number;
}

export async function getScores(): Promise<PortfolioScore[]> {
  const { data } = await api.get<PortfolioScore[]>("/v1/portfolio/scores");
  return data;
}

export async function getSummary(): Promise<PortfolioSummary> {
  const { data } = await api.get<PortfolioSummary>("/v1/portfolio/summary");
  return data;
}

export async function getBestCandidates(
  minScore = 70,
): Promise<PortfolioCandidate[]> {
  const { data } = await api.get<PortfolioCandidate[]>(
    "/v1/portfolio/best-candidates",
    { params: { min_score: minScore } },
  );
  return data;
}

export async function getFeatureMatrix(): Promise<FeatureMatrix> {
  const { data } = await api.get<FeatureMatrix>("/v1/portfolio/feature-matrix");
  return data;
}
