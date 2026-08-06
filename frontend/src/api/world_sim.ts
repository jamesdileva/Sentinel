import { api } from "./client";

export interface WorldSettlement {
  id: string;
  name: string;
  x: number;
  y: number;
  population: number;
  food: number;
  level: number;
  experience: number;
  skill_level: number;
  status: "active" | "abandoned";
  terrain: string;
  founded_day: number;
  destroyed_day: number | null;
  parent_id: string | null;
  farmers: number;
  builders: number;
  merchants: number;
  explorers: number;
}

export interface WorldRoad {
  from_id: string;
  to_id: string;
  built_day: number;
}

export interface WorldEvent {
  id: string;
  day: number;
  event_type: string;
  title: string;
  narrative: string;
  severity: number;
  affected_settlements: string[];
}

export interface WorldStats {
  settlements: number;
  active: number;
  abandoned: number;
  population: number;
  roads: number;
  events: number;
}

export interface WorldState {
  day_number: number;
  time_scale: number;
  seed: number;
  updated_at: string;
  settlements: WorldSettlement[];
  roads: WorldRoad[];
  recent_events: WorldEvent[];
  stats: WorldStats;
}

export interface WorldTickResult {
  days_advanced: number;
  day_number: number;
}

export async function getWorldState(): Promise<WorldState> {
  const { data } = await api.get<WorldState>("/v1/world-sim/state");
  return data;
}

export async function getWorldSettlement(
  settlementId: string,
): Promise<WorldSettlement & { roads: WorldRoad[] }> {
  const { data } = await api.get<WorldSettlement & { roads: WorldRoad[] }>(
    `/v1/world-sim/settlements/${settlementId}`,
  );
  return data;
}

export async function tickWorld(days: number): Promise<WorldTickResult> {
  const { data } = await api.post<WorldTickResult>("/v1/world-sim/tick", {
    days,
  });
  return data;
}

export async function resetWorld(
  seed?: number,
): Promise<{ status: string; seed: number }> {
  const { data } = await api.post<{ status: string; seed: number }>(
    "/v1/world-sim/reset",
    { seed: seed ?? null },
  );
  return data;
}

export async function accelerateWorld(
  timeScale: number,
): Promise<{ time_scale: number }> {
  const { data } = await api.post<{ time_scale: number }>(
    "/v1/world-sim/accelerate",
    { time_scale: timeScale },
  );
  return data;
}

export async function triggerWorldDisaster(
  settlementId: string,
  disasterType: string,
): Promise<{ settlement_id: string; disaster_type: string; applied: boolean }> {
  const { data } = await api.post<{
    settlement_id: string;
    disaster_type: string;
    applied: boolean;
  }>("/v1/world-sim/disaster", {
    settlement_id: settlementId,
    disaster_type: disasterType,
  });
  return data;
}
