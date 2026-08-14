import { api } from "./client";

import type { ArchitectureNode, GalaxyGraph, Timeline, TimelineEvent } from "../types";

export async function getGalaxy(): Promise<GalaxyGraph> {
  const { data } = await api.get<GalaxyGraph>("/v1/observatory/galaxy");
  return data;
}

export interface TimelineParams {
  days: number;
  kinds?: TimelineEvent["kind"][];
  projectId?: string;
  offset?: number;
  limit?: number;
}

export async function getTimeline(params: TimelineParams): Promise<Timeline> {
  const { data } = await api.get<Timeline>("/v1/observatory/timeline", {
    params: {
      days: params.days,
      kind: params.kinds?.length ? params.kinds.join(",") : undefined,
      project_id: params.projectId || undefined,
      offset: params.offset ?? 0,
      limit: params.limit ?? 100,
    },
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