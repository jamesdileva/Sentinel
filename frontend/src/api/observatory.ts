import { api } from "./client";

import type { ArchitectureNode, GalaxyGraph, Timeline } from "../types";

export async function getGalaxy(): Promise<GalaxyGraph> {
  const { data } = await api.get<GalaxyGraph>("/v1/observatory/galaxy");
  return data;
}

export async function getTimeline(days: number): Promise<Timeline> {
  const { data } = await api.get<Timeline>("/v1/observatory/timeline", {
    params: { days },
  });
  return data;
}

export async function getArchitecture(
  projectId: string,
): Promise<ArchitectureNode> {
  const { data } = await api.get<ArchitectureNode>(
    `/v1/observatory/architecture/${projectId}`,
  );
  return data;
}