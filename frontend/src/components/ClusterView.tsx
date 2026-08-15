import { useEffect, useMemo, useState } from "react";
import type { GalaxyGraph, GalaxyNode } from "../types";
import { getGalaxy } from "../api/observatory";
import FocusPanel from "./FocusPanel";
import { colorFor, usageCount } from "./galaxyShared";

const LABEL_W = 150;
const COL_W = 15;
const ROW_H = 18;
const HEADER_H = 48;
const DENDRO_H = 130;

interface TreeNode {
  id: string;
  height: number;
  members: string[];
  left?: TreeNode;
  right?: TreeNode;
}

function jaccard(a: Set<string>, b: Set<string>): number {
  let inter = 0;
  for (const x of a) if (b.has(x)) inter++;
  const union = a.size + b.size - inter;
  return union === 0 ? 0 : inter / union;
}

function minLabel(members: string[], byId: Map<string, GalaxyNode>): string {
  return members.map((id) => byId.get(id)!.label).sort()[0];
}

function clusterProjects(
  projects: GalaxyNode[],
  techOf: Map<string, Set<string>>,
  byId: Map<string, GalaxyNode>,
): TreeNode {
  let clusters = new Map<string, TreeNode>(
    projects.map((p) => [p.id, { id: p.id, height: 0, members: [p.id] }]),
  );
  const pairDist = (a: TreeNode, b: TreeNode) => {
    let sum = 0;
    let n = 0;
    for (const x of a.members)
      for (const y of b.members) {
        sum += 1 - jaccard(techOf.get(x)!, techOf.get(y)!);
        n++;
      }
    return n ? sum / n : 0;
  };
  while (clusters.size > 1) {
    const list = [...clusters.values()];
    let best: { d: number; key: string; a: TreeNode; b: TreeNode } | null = null;
    for (let i = 0; i < list.length; i++)
      for (let j = i + 1; j < list.length; j++) {
        const d = pairDist(list[i], list[j]);
        const key = `${minLabel(list[i].members, byId)}|${minLabel(
          list[j].members,
          byId,
        )}`;
        if (!best || d < best.d || (d === best.d && key < best.key)) {
          best = { d, key, a: list[i], b: list[j] };
        }
      }
    const merged: TreeNode = {
      id: `${best!.a.id}|${best!.b.id}`,
      height: best!.d / 2,
      members: [...best!.a.members, ...best!.b.members],
      left:
        minLabel(best!.a.members, byId) <= minLabel(best!.b.members, byId)
          ? best!.a
          : best!.b,
      right:
        minLabel(best!.a.members, byId) <= minLabel(best!.b.members, byId)
          ? best!.b
          : best!.a,
    };
    clusters.delete(best!.a.id);
    clusters.delete(best!.b.id);
    clusters.set(merged.id, merged);
  }
  return [...clusters.values()][0];
}

function leafOrder(t: TreeNode): string[] {
  if (!t.left) return [t.id];
  return [...leafOrder(t.left), ...leafOrder(t.right)];
}

function treeHeight(t: TreeNode): number {
  return Math.max(t.height, t.left ? treeHeight(t.left) : 0, t.right ? treeHeight(t.right) : 0);
}

export default function ClusterView() {
  const [graph, setGraph] = useState<GalaxyGraph | null>(null);
  const [active, setActive] = useState<string | null>(null);
  const [hover, setHover] = useState<{ row: string; col: string } | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getGalaxy()
      .then(setGraph)
      .catch((e) => setError(String(e)));
  }, []);

  const derived = useMemo(() => {
    if (!graph) return null;
    const byId = new Map(graph.nodes.map((n) => [n.id, n]));
    const techOf = new Map<string, Set<string>>();
    for (const link of graph.links) {
      const a = link.source;
      const b = link.target;
      const isTech = byId.get(b)?.kind === "tech";
      const projectId = isTech ? a : b;
      const techId = isTech ? b : a;
      if (byId.get(projectId)?.kind !== "project") continue;
      if (!techOf.has(projectId)) techOf.set(projectId, new Set());
      techOf.get(projectId)!.add(techId);
    }
    const projects = graph.nodes
      .filter((n) => n.kind === "project")
      .sort((a, b) => a.label.localeCompare(b.label));
    const techs = graph.nodes
      .filter((n) => n.kind === "tech")
      .sort((a, b) => usageCount(b.detail) - usageCount(a.detail));
    const tree =
      projects.length > 0 ? clusterProjects(projects, techOf, byId) : null;
    const rows = tree ? leafOrder(tree).map((id) => byId.get(id)!) : [];
    const maxH = tree ? treeHeight(tree) : 0;
    return { byId, techOf, techs, tree, rows, maxH };
  }, [graph]);

  if (error)
    return <p className="text-sm text-red-500">Galaxy failed to load: {error}</p>;
  if (!graph || !derived)
    return <p className="text-sm text-neutral-500">Loading galaxy…</p>;

  const { byId, techOf, techs, tree, rows, maxH } = derived;
  const svgW = LABEL_W + Math.max(1, techs.length) * COL_W + 20;
  const svgH = DENDRO_H + HEADER_H + Math.max(1, rows.length) * ROW_H + 10;

  const linkedTechs = (projectId: string) => techOf.get(projectId) ?? new Set<string>();
  const linkedProjects = (techId: string) => {
    const out = new Set<string>();
    for (const [pid, techs] of techOf) if (techs.has(techId)) out.add(pid);
    return out;
  };

  const focusNode = active ? byId.get(active) : undefined;

  const leafX = new Map<string, number>();
  rows.forEach((p, i) => leafX.set(p.id, LABEL_W + (i + 0.5) * COL_W));
  const leafY = DENDRO_H - 10;
  const nodeY = (t: TreeNode) =>
    leafY - (maxH > 0 ? (t.height / maxH) * (DENDRO_H - 30) : 0);

  const dendroSegments: React.ReactNode[] = [];
  const drawNode = (t: TreeNode): number => {
    if (!t.left) return leafX.get(t.id)!;
    const lx = drawNode(t.left);
    const rx = drawNode(t.right);
    const y = nodeY(t);
    dendroSegments.push(
      <line key={`v-${t.id}-l`} x1={lx} y1={nodeY(t.left!)} x2={lx} y2={y} stroke="#737373" strokeWidth={1} />,
      <line key={`v-${t.id}-r`} x1={rx} y1={nodeY(t.right!)} x2={rx} y2={y} stroke="#737373" strokeWidth={1} />,
      <line key={`h-${t.id}`} x1={lx} y1={y} x2={rx} y2={y} stroke="#737373" strokeWidth={1} />,
    );
    return (lx + rx) / 2;
  };
  if (tree && tree.left) drawNode(tree);

  const cellOpacity = (row: GalaxyNode, techId: string) => {
    if (!active) return hover ? 1 : 0.9;
    const activeNode = byId.get(active)!;
    if (activeNode.kind === "tech") {
      const shares = linkedProjects(active).has(row.id);
      return techId === active ? 1 : shares ? 1 : 0.2;
    }
    return row.id === active ? 1 : 0.2;
  };
  const labelOpacity = (row: GalaxyNode) => {
    if (!active) return 1;
    const activeNode = byId.get(active)!;
    if (activeNode.kind === "tech") return linkedProjects(active).has(row.id) ? 1 : 0.35;
    return row.id === active ? 1 : 0.35;
  };
  const techLabelOpacity = (techId: string) => {
    if (!active) return 1;
    const activeNode = byId.get(active)!;
    if (activeNode.kind === "project")
      return linkedTechs(active).has(techId) ? 1 : 0.35;
    return techId === active ? 1 : 0.35;
  };

  return (
    <div className="grid grid-cols-[1fr_auto] items-start gap-4">
      <div>
        <svg viewBox={`0 0 ${svgW} ${svgH}`} className="w-full select-none">
          {dendroSegments}
          {techs.map((t, i) => {
            const x = LABEL_W + (i + 0.5) * COL_W;
            const top = DENDRO_H - 4;
            return (
              <text
                key={t.id}
                data-tech-label={t.id}
                x={x}
                y={top + 22}
                opacity={techLabelOpacity(t.id)}
                transform={`rotate(-55 ${x} ${top + 22})`}
                textAnchor="end"
                className="cursor-pointer fill-slate-300 text-[10px]"
                onClick={() =>
                  setActive((current) => (current === t.id ? null : t.id))
                }
              >
                {t.label}
              </text>
            );
          })}
          {hover && (
            <>
              <rect
                data-row-hl="true"
                x={LABEL_W}
                y={DENDRO_H + HEADER_H + rows.findIndex((r) => r.id === hover.row) * ROW_H}
                width={techs.length * COL_W}
                height={ROW_H}
                fill="#ffffff"
                opacity={0.06}
              />
              <rect
                data-col-hl="true"
                x={LABEL_W + techs.findIndex((t) => t.id === hover.col) * COL_W + 1}
                y={DENDRO_H}
                width={COL_W - 2}
                height={HEADER_H + rows.length * ROW_H}
                fill="#ffffff"
                opacity={0.06}
              />
            </>
          )}
          {rows.map((row, r) => {
            const rowY = DENDRO_H + HEADER_H + r * ROW_H;
            return (
              <g key={row.id}>
                <text
                  data-project-label={row.id}
                  x={LABEL_W - 8}
                  y={rowY + ROW_H / 2 + 4}
                  opacity={labelOpacity(row)}
                  textAnchor="end"
                  paintOrder="stroke"
                  stroke="#0a0a0a"
                  strokeWidth={3}
                  className="cursor-pointer fill-slate-300 text-[11px]"
                  onClick={() =>
                    setActive((current) => (current === row.id ? null : row.id))
                  }
                >
                  {row.label}
                </text>
                {techs.map((t, c) => {
                  const used = techOf.get(row.id)?.has(t.id);
                  if (!used) return null;
                  const x = LABEL_W + c * COL_W;
                  return (
                    <rect
                      key={t.id}
                      data-cell="true"
                      data-row={row.id}
                      data-col={t.id}
                      x={x + 1}
                      y={rowY + 2}
                      width={COL_W - 2}
                      height={ROW_H - 4}
                      rx={2}
                      fill={colorFor(t.id)}
                      opacity={cellOpacity(row, t.id)}
                      className="cursor-pointer"
                      onMouseEnter={() => setHover({ row: row.id, col: t.id })}
                      onMouseLeave={() => setHover(null)}
                      onClick={() =>
                        setActive((current) =>
                          current === row.id ? null : row.id,
                        )
                      }
                    />
                  );
                })}
              </g>
            );
          })}
        </svg>
        <div className="mt-1 flex min-h-7 flex-wrap items-center gap-x-4 gap-y-1 text-xs text-neutral-400">
          <span className="flex items-center gap-1.5">
            <span className="h-3 w-3 rounded border border-neutral-800 bg-emerald-500" />
            Uses the technology
          </span>
          <span className="text-neutral-500">
            Tree = portfolio families · hover a cell · click a label to focus
          </span>
        </div>
        <ul data-testid="galaxy-tech-list" className="text-xs text-neutral-400">
          {techs.map((n) => (
            <li key={n.id}>
              <span className="text-amber-400">{n.label}</span> — {n.detail}
            </li>
          ))}
        </ul>
      </div>
      <FocusPanel
        node={focusNode}
        nodesById={byId}
        linkedTechs={linkedTechs}
        linkedProjects={linkedProjects}
        onClose={() => setActive(null)}
      />
    </div>
  );
}