import type { GalaxyNode } from "../types";

export const COLORS = [
  "#f59e0b",
  "#10b981",
  "#3b82f6",
  "#ec4899",
  "#8b5cf6",
  "#14b8a6",
  "#f97316",
];

export function colorFor(key: string): string {
  let hash = 5381;
  for (let i = 0; i < key.length; i++) hash = ((hash << 5) + hash + key.charCodeAt(i)) & 0xffffffff;
  return COLORS[Math.abs(hash) % COLORS.length];
}

export function usageCount(detail: string | null): number {
  const match = detail?.match(/used by (\d+) projects/);
  return match ? Number(match[1]) : 0;
}

export function tooltipFor(node: GalaxyNode): string {
  if (node.kind === "project")
    return node.detail ? `${node.label} (${node.detail})` : node.label;
  return `${node.label} — ${node.detail ?? ""}`;
}
