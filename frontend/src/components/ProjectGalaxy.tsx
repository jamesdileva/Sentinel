import { useEffect, useState } from "react";
import type { GalaxyGraph } from "../types";
import { getGalaxy } from "../api/observatory";

const COLORS = [
  "#f59e0b",
  "#10b981",
  "#3b82f6",
  "#ec4899",
  "#8b5cf6",
  "#14b8a6",
  "#f97316",
];

const nodeSize = (kind: string) => (kind === "project" ? 22 : 12);

export default function ProjectGalaxy({ height = 480 }: { height?: number }) {
  const [graph, setGraph] = useState<GalaxyGraph | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getGalaxy()
      .then(setGraph)
      .catch((e) => setError(String(e)));
  }, []);

  if (error)
    return (
      <p className="text-sm text-red-500">Galaxy failed to load: {error}</p>
    );
  if (!graph)
    return <p className="text-sm text-neutral-500">Loading galaxy…</p>;

  const techIds = new Set(
    graph.nodes.filter((n) => n.kind === "tech").map((n) => n.id),
  );
  const width = 800;
  const projectCount = graph.nodes.filter((n) => n.kind === "project").length;
  const projectSpacing = (height - 60) / (projectCount + 1);
  const techSpacing = (height - 80) / (techIds.size + 1);

  const positions = new Map<string, { x: number; y: number }>();
  let pi = 0;
  let ti = 0;
  for (const node of graph.nodes) {
    if (node.kind === "project") {
      positions.set(node.id, { x: 40, y: 30 + projectSpacing * (pi + 1) });
      pi++;
    } else {
      positions.set(node.id, { x: width - 60, y: 40 + techSpacing * (ti + 1) });
      ti++;
    }
  }

  return (
    <div>
      <svg viewBox={`0 0 ${width} ${height}`} className="w-full">
        {graph.links.map((link) => {
          const s = positions.get(link.source);
          const t = positions.get(link.target);
          if (!s || !t) return null;
          return (
            <line
              key={`${link.source}-${link.target}`}
              x1={s.x}
              y1={s.y}
              x2={t.x}
              y2={t.y}
              stroke="#a3a3a3"
              strokeWidth={1.5}
            />
          );
        })}
        {graph.nodes.map((node) => {
          const pos = positions.get(node.id);
          if (!pos) return null;
          const r = nodeSize(node.kind);
          const color = COLORS[node.id.length % COLORS.length];
          return (
            <g key={node.id}>
              <title>
                {node.label}
                {node.detail ? ` — ${node.detail}` : ""}
              </title>
              <circle
                cx={pos.x}
                cy={pos.y}
                r={r}
                fill="#1e1e1e"
                stroke={color}
                strokeWidth={2}
              />
              <text
                x={pos.x + r + 6}
                y={pos.y + 4}
                className="fill-slate-500 text-[12px]"
              >
                {node.label}
              </text>
            </g>
          );
        })}
      </svg>
      <ul className="mt-1 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-neutral-400">
        <li className="flex items-center gap-1.5">
          <span className="h-3.5 w-3.5 rounded-full border-2 border-amber-500 bg-neutral-800" />
          Project
        </li>
        <li className="flex items-center gap-1.5">
          <span className="h-2 w-2 rounded-full border-2 border-emerald-500 bg-neutral-800" />
          Technology / dependency
        </li>
        <li className="flex items-center gap-1.5">
          <span className="h-0.5 w-5 bg-neutral-400" /> Shares a technology
        </li>
      </ul>
      <ul className="text-xs text-neutral-400">
        {graph.nodes
          .filter((n) => n.kind === "tech")
          .map((n) => (
            <li key={n.id}>
              <span className="text-amber-400">{n.label}</span> — {n.detail}
            </li>
          ))}
      </ul>
    </div>
  );
}
