/**
 * GalaxyView — force-directed map of the project/tech graph (v1.17.18.6).
 *
 * One visual replacing metro+families: projects are planets sized by how
 * many technologies they use, techs are smaller satellites, shared techs
 * draw gravity links so related projects physically cluster ("families"
 * emerge from layout instead of a separate dendrogram). Layout is a small
 * deterministic force simulation — no new dependencies.
 *
 * Interactions: click / Enter+Space focuses a node (FocusPanel), hover
 * previews neighbors, non-neighbors dim while focused. The SVG viewBox is
 * sized to its container, so window resizing scales instead of clipping.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { GalaxyGraph, GalaxyNode } from "../types";
import FocusPanel from "./FocusPanel";
import { colorFor, tooltipFor, usageCount } from "./galaxyShared";

interface SimNode {
  id: string;
  node: GalaxyNode;
  x: number;
  y: number;
  vx: number;
  vy: number;
  r: number;
  color: string;
}

interface LinkPair {
  source: SimNode;
  target: SimNode;
  color: string;
}

const REPULSION = 3600;
const LINK_DISTANCE = 120;
const LINK_STRENGTH = 0.06;
const CENTER_PULL = 0.02;
const DAMPING = 0.8;
const ITERATIONS = 320;
// v1.17.18.6 polish: nodes feel an inward push inside this band instead of
// being hard-clamped onto the border (edge-pinned planets artifact).
const EDGE_PAD = 52;

// Resizable canvas heights (user-tunable; width always follows container).
const HEIGHT_PRESETS = { compact: 400, normal: 560, tall: 720 } as const;
type HeightPreset = keyof typeof HEIGHT_PRESETS;

function dominantTechColor(graph: GalaxyGraph, projectId: string): string {
  let bestTech: string | null = null;
  let bestUse = -1;
  for (const link of graph.links) {
    const techId =
      link.source === projectId
        ? link.target
        : link.target === projectId
          ? link.source
          : null;
    if (!techId) continue;
    const use = usageCount(
      graph.nodes.find((n) => n.id === techId)?.detail ?? null,
    );
    if (use > bestUse) {
      bestUse = use;
      bestTech = techId;
    }
  }
  return bestTech ? colorFor(bestTech) : "#94a3b8";
}

function buildSim(
  graph: GalaxyGraph,
  width: number,
  height: number,
): { nodes: SimNode[]; links: LinkPair[] } {
  const degree = new Map<string, number>();
  for (const link of graph.links) {
    degree.set(link.source, (degree.get(link.source) ?? 0) + 1);
    degree.set(link.target, (degree.get(link.target) ?? 0) + 1);
  }
  const count = Math.max(graph.nodes.length, 1);
  const cx = width / 2;
  const cy = height / 2;
  const nodes: SimNode[] = graph.nodes.map((node, i) => {
    const angle = (i / count) * Math.PI * 2;
    const radius = 55 + ((i * 37) % Math.max(120, count));
    const d = degree.get(node.id) ?? 0;
    const isTech = node.kind === "tech";
    return {
      id: node.id,
      node,
      x: cx + Math.cos(angle) * radius,
      y: cy + Math.sin(angle) * radius,
      vx: 0,
      vy: 0,
      r: isTech
        ? 5 + Math.min(usageCount(node.detail), 12)
        : 9 + Math.min(d, 10) * 1.4,
      color: isTech ? colorFor(node.id) : dominantTechColor(graph, node.id),
    };
  });
  const simById = new Map(nodes.map((n) => [n.id, n]));
  const links: LinkPair[] = [];
  for (const link of graph.links) {
    const source = simById.get(link.source);
    const target = simById.get(link.target);
    if (!source || !target) continue;
    links.push({ source, target, color: colorFor(link.tech) });
  }
  return { nodes, links };
}

function simulate(
  nodes: SimNode[],
  links: LinkPair[],
  width: number,
  height: number,
): void {
  const cx = width / 2;
  const cy = height / 2;
  for (let step = 0; step < ITERATIONS; step++) {
    const alpha = Math.pow(0.998, step); // decays 320 -> ~0.53; keeps late ticks gentle
    for (let i = 0; i < nodes.length; i++) {
      const a = nodes[i];
      for (let j = i + 1; j < nodes.length; j++) {
        const b = nodes[j];
        let dx = b.x - a.x;
        let dy = b.y - a.y;
        let d2 = dx * dx + dy * dy;
        if (d2 < 1) {
          dx = (i - j) * 0.5;
          dy = (i % 3) * 0.5 - (j % 2) * 0.5;
          d2 = 1;
        }
        const f = (REPULSION * alpha) / d2;
        const d = Math.sqrt(d2);
        const fx = (dx / d) * f;
        const fy = (dy / d) * f;
        a.vx -= fx;
        a.vy -= fy;
        b.vx += fx;
        b.vy += fy;
      }
    }
    for (const link of links) {
      const dx = link.target.x - link.source.x;
      const dy = link.target.y - link.source.y;
      const dist = Math.sqrt(dx * dx + dy * dy) || 1;
      const f = ((dist - LINK_DISTANCE) / dist) * LINK_STRENGTH * alpha;
      link.source.vx += dx * f;
      link.source.vy += dy * f;
      link.target.vx -= dx * f;
      link.target.vy -= dy * f;
    }
    const margin = 10;
    for (const n of nodes) {
      n.vx += (cx - n.x) * CENTER_PULL * alpha;
      n.vy += (cy - n.y) * CENTER_PULL * alpha;
      // soft boundary (polish): inward push in the edge band, no hard clamp
      if (n.x < EDGE_PAD) n.vx += (EDGE_PAD - n.x) * 0.09;
      if (n.x > width - EDGE_PAD) n.vx -= (n.x - (width - EDGE_PAD)) * 0.09;
      if (n.y < EDGE_PAD) n.vy += (EDGE_PAD - n.y) * 0.09;
      if (n.y > height - EDGE_PAD) n.vy -= (n.y - (height - EDGE_PAD)) * 0.09;
      n.vx *= DAMPING;
      n.vy *= DAMPING;
      n.x += n.vx;
      n.y += n.vy;
      // last-resort containment only
      n.x = Math.max(margin, Math.min(width - margin, n.x));
      n.y = Math.max(margin, Math.min(height - margin, n.y));
    }
  }
  // polish: resolve circle overlaps so nodes stop stacking (the screenshot's
  // merged purple pair). Half-overlap separation, a few relaxation passes.
  for (let pass = 0; pass < 50; pass++) {
    let moved = false;
    for (let i = 0; i < nodes.length; i++) {
      const a = nodes[i];
      for (let j = i + 1; j < nodes.length; j++) {
        const b = nodes[j];
        const dx = b.x - a.x;
        const dy = b.y - a.y;
        const minDist = a.r + b.r + 8;
        const d2 = dx * dx + dy * dy;
        if (d2 >= minDist * minDist || d2 === 0) continue;
        const d = Math.sqrt(d2);
        const push = (minDist - d) / 2;
        const ux = dx / d || 0.1;
        const uy = dy / d || 0.1;
        a.x -= ux * push;
        a.y -= uy * push;
        b.x += ux * push;
        b.y += uy * push;
        moved = true;
      }
    }
    if (!moved) break;
  }
}

export default function GalaxyView({ graph }: { graph: GalaxyGraph }) {
  const wrapRef = useRef<HTMLDivElement | null>(null);
  const [size, setSize] = useState<{ w: number; h: number }>({
    w: 900,
    h: HEIGHT_PRESETS.normal,
  });
  const [preset, setPreset] = useState<HeightPreset>("normal");
  const [active, setActive] = useState<string | null>(null);
  const [hovered, setHovered] = useState<string | null>(null);

  // Responsive sizing: width follows the container; height is user-tunable
  // (Compact/Normal/Tall). The SVG viewBox is set to actual pixels so
  // window resizes scale the map instead of clipping it.
  useEffect(() => {
    const el = wrapRef.current;
    if (!el || typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(() => {
      const w = el.clientWidth;
      if (w > 0) setSize((prev) => ({ ...prev, w }));
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  useEffect(() => {
    setSize((prev) => ({ ...prev, h: HEIGHT_PRESETS[preset] }));
  }, [preset]);

  const { nodes, links } = useMemo(() => {
    const sim = buildSim(graph, size.w, size.h);
    simulate(sim.nodes, sim.links, size.w, size.h);
    return sim;
  }, [graph, size]);

  // polish: greedy label placement — hide a project label that would
  // overlap an already-placed one (bigger nodes keep priority), fixing the
  // stacked "Jamesdileva…"/"Dinner Menu" labels from the first pass.
  const labelVisible = useMemo(() => {
    const visible = new Map<string, boolean>();
    const placed: Array<{ x0: number; x1: number; y0: number; y1: number }> = [];
    for (const sim of nodes) {
      if (sim.node.kind !== "project") continue;
      const halfW = sim.node.label.length * 3.3 + 8;
      const box = {
        x0: sim.x - halfW,
        x1: sim.x + halfW,
        y0: sim.y + sim.r,
        y1: sim.y + sim.r + 15,
      };
      const clash = placed.some(
        (p) =>
          !(box.x1 < p.x0 || box.x0 > p.x1 || box.y1 < p.y0 || box.y0 > p.y1),
      );
      visible.set(sim.id, !clash);
      if (!clash) placed.push(box);
    }
    return visible;
  }, [nodes]);

  const nodesById = useMemo(
    () => new Map<string, GalaxyNode>(graph.nodes.map((n) => [n.id, n])),
    [graph],
  );
  const neighborsOf = useMemo(() => {
    const m = new Map<string, Set<string>>();
    for (const link of graph.links) {
      if (!m.has(link.source)) m.set(link.source, new Set());
      if (!m.has(link.target)) m.set(link.target, new Set());
      m.get(link.source)!.add(link.target);
      m.get(link.target)!.add(link.source);
    }
    return m;
  }, [graph]);

  const linkedTechs = useCallback(
    (projectId: string) => neighborsOf.get(projectId) ?? new Set<string>(),
    [neighborsOf],
  );
  const linkedProjects = useCallback(
    (techId: string) => neighborsOf.get(techId) ?? new Set<string>(),
    [neighborsOf],
  );

  const focusNeighbors =
    active !== null ? (neighborsOf.get(active) ?? new Set<string>()) : null;
  const isLit = (id: string): boolean =>
    focusNeighbors === null ||
    id === active ||
    focusNeighbors.has(id) ||
    id === hovered;

  const toggle = (id: string): void =>
    setActive((current) => (current === id ? null : id));

  return (
    <div className="flex items-start gap-4">
      <div ref={wrapRef} className="min-w-0 flex-1">
        <div className="mb-2 flex items-center justify-between">
          <p className="text-[11px] text-neutral-500">
            click a node to focus · hover to preview
          </p>
          <div
            className="flex gap-1 text-[11px]"
            role="group"
            aria-label="Map height"
          >
            {(Object.keys(HEIGHT_PRESETS) as HeightPreset[]).map((key) => (
              <button
                key={key}
                onClick={() => setPreset(key)}
                aria-pressed={preset === key}
                className={`rounded px-2 py-0.5 capitalize ${
                  preset === key
                    ? "bg-neutral-700 text-white"
                    : "text-neutral-500 hover:text-neutral-300"
                }`}
              >
                {key}
              </button>
            ))}
          </div>
        </div>
        <svg
          viewBox={`0 0 ${size.w} ${size.h}`}
          style={{ height: size.h }}
          className="w-full select-none rounded-lg border border-neutral-800"
          role="img"
          aria-label="Force-directed map of projects and shared technologies"
        >
          <defs>
            <radialGradient id="galaxy-bg" cx="50%" cy="42%" r="78%">
              <stop offset="0%" stopColor="#12172b" />
              <stop offset="100%" stopColor="#0a0a0a" />
            </radialGradient>
          </defs>
          <rect x={0} y={0} width={size.w} height={size.h} fill="url(#galaxy-bg)" />
          {links.map((link, i) => {
            const lit =
              active !== null &&
              (link.source.id === active || link.target.id === active);
            return (
              <line
                key={`l${i}`}
                x1={link.source.x}
                y1={link.source.y}
                x2={link.target.x}
                y2={link.target.y}
                stroke={link.color}
                strokeWidth={lit ? 1.6 : 1}
                opacity={active === null ? 0.16 : lit ? 0.5 : 0.05}
              />
            );
          })}
          {[...nodes].reverse().map((sim) => {
            const node = sim.node;
            const lit = isLit(sim.id);
            const labelClash = labelVisible.get(sim.id) === false;
            const showLabel =
              (node.kind === "project" && !labelClash) ||
              hovered === sim.id ||
              sim.id === active;
            return (
              <g
                key={node.id}
                role="button"
                tabIndex={0}
                aria-label={`${node.label} (${node.kind})`}
                opacity={lit ? 1 : 0.14}
                className="cursor-pointer focus:outline-none"
                onClick={() => toggle(sim.id)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    toggle(sim.id);
                  }
                }}
                onMouseEnter={() => setHovered(sim.id)}
                onMouseLeave={() => setHovered(null)}
              >
                <title>{tooltipFor(node)}</title>
                <circle cx={sim.x} cy={sim.y} r={sim.r} fill={sim.color}>
                  {/* focus ring via stroke keeps markup light */}
                  {sim.id === active && (
                    <animate attributeName="r" values={`${sim.r};${sim.r + 2};${sim.r}`} dur="1.2s" repeatCount="indefinite" />
                  )}
                </circle>
                {node.kind === "tech" && (
                  <circle cx={sim.x} cy={sim.y} r={Math.max(2, sim.r - 2.5)} fill="#0a0a0a" opacity={0.35} />
                )}
                {showLabel && (
                  <text
                    x={sim.x}
                    y={sim.y + sim.r + 12}
                    textAnchor="middle"
                    className={
                      node.kind === "project"
                        ? "pointer-events-none fill-neutral-200 text-[11px] font-medium"
                        : "pointer-events-none fill-neutral-400 text-[10px]"
                    }
                  >
                    {node.label}
                  </text>
                )}
              </g>
            );
          })}
        </svg>
      </div>
      <FocusPanel
        node={active !== null ? nodesById.get(active) : undefined}
        nodesById={nodesById}
        linkedTechs={linkedTechs}
        linkedProjects={linkedProjects}
        onClose={() => setActive(null)}
      />
    </div>
  );
}
