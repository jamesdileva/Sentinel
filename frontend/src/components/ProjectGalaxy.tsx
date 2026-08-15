import { useEffect, useMemo, useState } from "react";
import type { GalaxyGraph, GalaxyNode } from "../types";
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

const WIDTH = 900;
const PROJECT_X = 110;
const TECH_X = 850;
const LINK_DIM = 0.12;
const LINK_REST = 0.45;

const nodeSize = (kind: string) => (kind === "project" ? 26 : 12);

function usageCount(detail: string | null): number {
  const match = detail?.match(/used by (\d+) projects/);
  return match ? Number(match[1]) : 0;
}

function defaultLayout(graph: GalaxyGraph, height: number): Map<string, { x: number; y: number }> {
  const projects = graph.nodes.filter((n) => n.kind === "project");
  const techs = graph.nodes.filter((n) => n.kind === "tech");
  const positions = new Map<string, { x: number; y: number }>();
  const projectSpacing = (height - 60) / (projects.length + 1);
  projects.forEach((node, i) => {
    positions.set(node.id, { x: PROJECT_X, y: 30 + projectSpacing * (i + 1) });
  });
  const techSpacing = (height - 80) / (techs.length + 1);
  techs.forEach((node, i) => {
    positions.set(node.id, { x: TECH_X, y: 40 + techSpacing * (i + 1) });
  });
  return positions;
}

export default function ProjectGalaxy({ height = 480 }: { height?: number }) {
  const [graph, setGraph] = useState<GalaxyGraph | null>(null);
  const [positions, setPositions] = useState<Map<string, { x: number; y: number }>>(
    new Map(),
  );
  const [active, setActive] = useState<string | null>(null);
  const [hovered, setHovered] = useState<string | null>(null);
  const [layoutDirty, setLayoutDirty] = useState(false);
  const [drag, setDrag] = useState<{
    id: string;
    baseX: number;
    baseY: number;
    clientX: number;
    clientY: number;
  } | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getGalaxy()
      .then((g) => {
        setGraph(g);
        setPositions(defaultLayout(g, height));
      })
      .catch((e) => setError(String(e)));
  }, [height]);

  const nodesById = useMemo(
    () => new Map((graph?.nodes ?? []).map((n) => [n.id, n])),
    [graph],
  );

  if (error)
    return (
      <p className="text-sm text-red-500">Galaxy failed to load: {error}</p>
    );
  if (!graph)
    return <p className="text-sm text-neutral-500">Loading galaxy…</p>;

  const projectsWithLinks = new Set(graph.links.map((link) => link.source));
  const linkedTechs = (projectId: string) =>
    new Set(
      graph.links
        .filter(
          (link) => link.source === projectId || link.target === projectId,
        )
        .map((link) => (link.source === projectId ? link.target : link.source)),
    );
  // tech nodes are identified by their node id ("t:react"); links carry the
  // tech *name* ("react"), so resolve through the target node instead of
  // string-matching.
  const linkedProjects = (techNodeId: string) =>
    new Set(
      graph.links
        .filter(
          (link) =>
            nodesById.get(link.target)?.kind === "tech" &&
            link.target === techNodeId,
        )
        .map((link) => link.source),
    );

  const focus = hovered ?? active;

  const nodeOpacity = (node: GalaxyNode) => {
    if (node.kind === "project") {
      if (!projectsWithLinks.has(node.id)) return 0.35;
      if (!focus) return 1;
      if (nodesById.get(focus)?.kind === "project")
        return node.id === focus ? 1 : 0.2;
      return linkedProjects(focus).has(node.id) ? 1 : 0.2;
    }
    if (!focus) return 1;
    if (nodesById.get(focus)?.kind === "project")
      return linkedTechs(focus).has(node.id) ? 1 : 0.2;
    return node.id === focus ? 1 : 0.2;
  };

  const linkOpacity = (link: { source: string; target: string; tech: string }) => {
    if (!focus) return LINK_REST;
    if (nodesById.get(focus)?.kind === "project")
      return link.source === focus || link.target === focus ? 1 : LINK_DIM;
    return link.target === focus ? 1 : LINK_DIM;
  };

  const resetLayout = () => {
    setPositions(defaultLayout(graph, height));
    setLayoutDirty(false);
    setActive(null);
  };

  const onPointerDown = (
    node: GalaxyNode,
    e: React.PointerEvent<SVGGElement>,
  ) => {
    e.preventDefault();
    (e.currentTarget as SVGGElement).setPointerCapture?.(e.pointerId);
    const pos = positions.get(node.id) ?? { x: 0, y: 0 };
    setDrag({
      id: node.id,
      baseX: pos.x,
      baseY: pos.y,
      clientX: e.clientX,
      clientY: e.clientY,
    });
  };

  const onPointerMove = (e: React.PointerEvent<SVGGElement>) => {
    if (!drag) return;
    const rect = e.currentTarget.ownerSVGElement?.getBoundingClientRect();
    const scaleX = rect && rect.width > 0 ? WIDTH / rect.width : 1;
    const scaleY = rect && rect.height > 0 ? height / rect.height : 1;
    const x = drag.baseX + (e.clientX - drag.clientX) * scaleX;
    const y = drag.baseY + (e.clientY - drag.clientY) * scaleY;
    const clamped = {
      x: Math.min(WIDTH - 30, Math.max(30, x)),
      y: Math.min(height - 25, Math.max(25, y)),
    };
    setPositions((prev) => {
      const next = new Map(prev);
      next.set(drag.id, clamped);
      return next;
    });
    setLayoutDirty(true);
  };

  const onPointerUp = () => setDrag(null);

  const techList = [...graph.nodes]
    .filter((n) => n.kind === "tech")
    .sort((a, b) => usageCount(b.detail) - usageCount(a.detail));

  const focusNode = focus ? nodesById.get(focus) : undefined;

  return (
    <div>
      <div className="flex gap-4">
        <svg viewBox={`0 0 ${WIDTH} ${height}`} className="w-full select-none">
          {graph.links.map((link) => {
            const s = positions.get(link.source);
            const t = positions.get(link.target);
            if (!s || !t) return null;
            const midX = (s.x + t.x) / 2;
            const midY = (s.y + t.y) / 2 + 14;
            return (
              <path
                key={`${link.source}-${link.target}`}
                data-link="true"
                d={`M ${s.x} ${s.y} Q ${midX} ${midY} ${t.x} ${t.y}`}
                fill="none"
                stroke="#a3a3a3"
                strokeWidth={1.2}
                opacity={linkOpacity(link)}
              />
            );
          })}
          {graph.nodes.map((node) => {
            const pos = positions.get(node.id);
            if (!pos) return null;
            const r = nodeSize(node.kind);
            const color = COLORS[node.id.length % COLORS.length];
            const isProject = node.kind === "project";
            const tooltip = isProject
              ? node.detail
                ? `${node.label} (${node.detail})`
                : node.label
              : `${node.label} — ${node.detail ?? ""}`;
            const labelX = isProject ? PROJECT_X - 10 : pos.x - r - 7;
            return (
              <g
                key={node.id}
                data-kind={node.kind}
                data-id={node.id}
                opacity={nodeOpacity(node)}
                className={drag?.id === node.id ? "cursor-grabbing" : "cursor-grab"}
                onClick={() => setActive((current) => (current === node.id ? null : node.id))}
                onMouseEnter={() => setHovered(node.id)}
                onMouseLeave={() => setHovered(null)}
                onPointerDown={(e) => onPointerDown(node, e)}
                onPointerMove={onPointerMove}
                onPointerUp={onPointerUp}
              >
                <title>{tooltip}</title>
                {isProject ? (
                  <circle
                    cx={pos.x}
                    cy={pos.y}
                    r={r}
                    fill="#1e1e1e"
                    stroke={color}
                    strokeWidth={2.5}
                  />
                ) : (
                  <rect
                    x={pos.x - 9}
                    y={pos.y - 9}
                    width={18}
                    height={18}
                    rx={2}
                    transform={`rotate(45 ${pos.x} ${pos.y})`}
                    fill={color}
                    stroke="#1e1e1e"
                    strokeWidth={1.5}
                  />
                )}
                <text
                  x={labelX}
                  y={pos.y + 4}
                  textAnchor="end"
                  paintOrder="stroke"
                  stroke="#0a0a0a"
                  strokeWidth={3.5}
                  className="fill-slate-300 text-[12px]"
                >
                  {node.label}
                </text>
              </g>
            );
          })}
        </svg>
        {focusNode && (
          <aside className="w-60 shrink-0 rounded border border-neutral-800 bg-neutral-900 p-3 text-xs">
            <div className="flex items-start justify-between gap-2">
              <div>
                <h3 className="text-base font-semibold text-white">
                  {focusNode.label}
                </h3>
                {focusNode.kind === "project" ? (
                  <p className="mt-0.5 text-neutral-400">
                    {[focusNode.detail, focusNode.framework]
                      .filter(Boolean)
                      .join(" · ") || "no metadata"}
                  </p>
                ) : (
                  <p className="mt-0.5 text-neutral-400">{focusNode.detail}</p>
                )}
              </div>
              <button
                onClick={() => setActive(null)}
                className="text-neutral-500 hover:text-neutral-300"
                aria-label="Clear focus"
              >
                ×
              </button>
            </div>
            <div className="mt-3">
              <p className="font-medium text-neutral-300">
                {focusNode.kind === "project" ? "Shared technologies" : "Used by"}
              </p>
              <ul className="mt-1 space-y-1 text-neutral-400">
                {(focusNode.kind === "project"
                  ? [...linkedTechs(focusNode.id)]
                      .map((id) => nodesById.get(id))
                      .filter((n): n is GalaxyNode => Boolean(n))
                      .sort((a, b) => usageCount(b.detail) - usageCount(a.detail))
                  : [...linkedProjects(focusNode.id)]
                      .map((id) => nodesById.get(id))
                      .filter((n): n is GalaxyNode => Boolean(n))
                      .sort((a, b) => a.label.localeCompare(b.label))
                ).map((n) => (
                  <li key={n.id}>
                    <span className="text-amber-400">{n.label}</span>
                    {n.detail && ` — ${n.detail}`}
                  </li>
                ))}
              </ul>
            </div>
          </aside>
        )}
      </div>
      <ul className="mt-1 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-neutral-400">
        <li className="flex items-center gap-1.5">
          <span className="h-3.5 w-3.5 rounded-full border-2 border-amber-500 bg-neutral-800" />
          Project
        </li>
        <li className="flex items-center gap-1.5">
          <span className="h-2 w-2 rotate-45 border border-neutral-800 bg-emerald-500" />
          Technology / dependency
        </li>
        <li className="flex items-center gap-1.5">
          <span className="h-0.5 w-5 bg-neutral-400" /> Shares a technology
        </li>
        <li className="text-neutral-500">
          Hover or click to focus · drag to rearrange
        </li>
        {(active || layoutDirty) && (
          <li>
            <button
              onClick={resetLayout}
              className="rounded border border-neutral-700 px-1.5 py-0.5 text-neutral-400 hover:text-neutral-200"
            >
              Reset layout
            </button>
          </li>
        )}
      </ul>
      <ul data-testid="galaxy-tech-list" className="text-xs text-neutral-400">
        {techList.map((n) => (
          <li key={n.id}>
            <span className="text-amber-400">{n.label}</span> — {n.detail}
          </li>
        ))}
      </ul>
    </div>
  );
}