import { useMemo, useState } from "react";
import type { GalaxyGraph, GalaxyNode } from "../types";
import FocusPanel from "./FocusPanel";
import { colorFor, tooltipFor, usageCount } from "./galaxyShared";

const WIDTH = 1200;
const MARGIN_X = 40;
const SLOT_STEP = 100;
const ROW_GAP = 30;
const TOP = 30;
const LABEL_W = 150;

interface Station {
  project: GalaxyNode;
  lineIds: string[];
  primary: string;
  x: number;
}

export default function MetroView({ graph, height = 520 }: { graph: GalaxyGraph; height?: number }) {
  const [lineCount, setLineCount] = useState(15);
  const [positions, setPositions] = useState<Map<string, number>>(() => defaultPositions(graph));
  const [active, setActive] = useState<string | null>(null);
  const [hovered, setHovered] = useState<string | null>(null);
  const [layoutDirty, setLayoutDirty] = useState(false);
  const [drag, setDrag] = useState<{
    id: string;
    baseX: number;
    clientX: number;
  } | null>(null);

  const layout = useMemo(() => {
    const techs = graph.nodes
      .filter((n) => n.kind === "tech")
      .sort((a, b) => usageCount(b.detail) - usageCount(a.detail));
    const lines = techs.slice(0, lineCount);
    const lineIndex = new Map(lines.map((t, i) => [t.id, i]));
    const techLinks = new Map<string, Set<string>>();
    for (const link of graph.links) {
      if (!techLinks.has(link.source)) techLinks.set(link.source, new Set());
      if (!techLinks.has(link.target)) techLinks.set(link.target, new Set());
      techLinks.get(link.source)!.add(link.target);
      techLinks.get(link.target)!.add(link.source);
    }
    const projects = graph.nodes
      .filter((n) => n.kind === "project")
      .map((project) => {
        const lineIds = [...(techLinks.get(project.id) ?? [])]
          .filter((id) => lineIndex.has(id))
          .sort((a, b) => lineIndex.get(a)! - lineIndex.get(b)!);
        return { project, lineIds, primary: lineIds[0] ?? null };
      });
    const served = projects
      .filter((p) => p.lineIds.length > 0)
      .sort((a, b) => {
        const ai = lineIndex.get(a.primary)!;
        const bi = lineIndex.get(b.primary)!;
        return ai !== bi ? ai - bi : a.project.label.localeCompare(b.project.label);
      });
    let slot = 0;
    const stations = new Map<string, Station>();
    for (const p of served) {
      stations.set(p.project.id, {
        project: p.project,
        lineIds: p.lineIds,
        primary: p.primary!,
        x: positions.get(p.project.id) ?? MARGIN_X + slot * SLOT_STEP,
      });
      slot++;
    }
    const unserved = projects
      .filter((p) => p.lineIds.length === 0)
      .map((p) => p.project);
    return { lines, lineIndex, stations, unserved, techLinks, projects };
  }, [graph, lineCount, positions]);

  const nodesById = useMemo(
    () => new Map((graph?.nodes ?? []).map((n) => [n.id, n])),
    [graph],
  );

  if (!layout) return <p className="text-sm text-neutral-500">Loading galaxy…</p>;

  const { lines, lineIndex, stations, unserved, techLinks, projects } = layout;
  const svgH = Math.max(height, TOP + lines.length * ROW_GAP + 40);
  const focus = active ?? hovered;

  const linkedTechs = (projectId: string) =>
    new Set([...(techLinks.get(projectId) ?? [])]);

  const linkedProjects = (techId: string) => {
    const out = new Set<string>();
    for (const [source, techs] of techLinks) {
      if (techs.has(techId)) out.add(source);
    }
    return out;
  };

  const railOpacity = (lineId: string) => {
    if (!focus) return 1;
    if (nodesById.get(focus)?.kind === "tech") return lineId === focus ? 1 : 0.15;
    const station = stations.get(focus);
    return station?.lineIds.includes(lineId) ? 1 : 0.15;
  };

  const stationOpacity = (station: Station) => {
    if (!focus) return 1;
    if (nodesById.get(focus)?.kind === "project")
      return station.project.id === focus ? 1 : 0.25;
    return station.lineIds.includes(focus) ? 1 : 0.25;
  };

  const resetLayout = () => {
    setPositions(defaultPositions(graph));
    setLayoutDirty(false);
    setActive(null);
  };

  const onPointerDown = (
    station: Station,
    e: React.PointerEvent<SVGGElement>,
  ) => {
    e.preventDefault();
    (e.currentTarget as SVGGElement).setPointerCapture?.(e.pointerId);
    setDrag({ id: station.project.id, baseX: station.x, clientX: e.clientX });
  };

  const onPointerMove = (e: React.PointerEvent<SVGGElement>) => {
    if (!drag) return;
    const rect = e.currentTarget.ownerSVGElement?.getBoundingClientRect();
    const scaleX = rect && rect.width > 0 ? WIDTH / rect.width : 1;
    const x = drag.baseX + (e.clientX - drag.clientX) * scaleX;
    const clamped = Math.min(WIDTH - LABEL_W - 20, Math.max(30, x));
    setPositions((prev) => {
      const next = new Map(prev);
      next.set(drag.id, clamped);
      return next;
    });
    setLayoutDirty(true);
  };

  const onPointerUp = () => setDrag(null);

  const focusNode = focus ? nodesById.get(focus) : undefined;
  const techList = [...graph.nodes]
    .filter((n) => n.kind === "tech")
    .sort((a, b) => usageCount(b.detail) - usageCount(a.detail));

  return (
    <div className="grid grid-cols-[1fr_auto] items-start gap-4">
      <div>
        <div className="flex items-center gap-3 text-xs text-neutral-400">
          <span>Show top</span>
          <input
            type="range"
            min={1}
            max={Math.max(1, projects.length > 0 ? techList.length : 1)}
            value={lineCount}
            onChange={(e) => setLineCount(Number(e.target.value))}
            className="w-40"
            aria-label="Lines shown"
          />
          <span>
            {Math.min(lineCount, techList.length)} of {techList.length} techs
          </span>
        </div>
        <svg viewBox={`0 0 ${WIDTH} ${svgH}`} className="mt-2 w-full select-none">
          {lines.map((line, i) => {
            const y = TOP + i * ROW_GAP;
            const color = colorFor(line.id);
            return (
              <g
                key={line.id}
                data-line={line.id}
                opacity={railOpacity(line.id)}
                className="cursor-pointer"
                onClick={() =>
                  setActive((current) => (current === line.id ? null : line.id))
                }
              >
                <line
                  x1={20}
                  x2={WIDTH - LABEL_W}
                  y1={y}
                  y2={y}
                  stroke={color}
                  strokeWidth={3}
                  data-rail="true"
                />
                <line
                  x1={20}
                  x2={WIDTH - LABEL_W}
                  y1={y}
                  y2={y}
                  stroke="#000000"
                  strokeWidth={7}
                  opacity={0.25}
                />
                <text
                  x={WIDTH - LABEL_W + 10}
                  y={y + 4}
                  className="fill-slate-300 text-[11px]"
                >
                  {line.label} · {usageCount(line.detail)}
                </text>
              </g>
            );
          })}
          {[...stations.values()].map((station) => {
            const topLine = lineIndex.get(station.primary)!;
            const bottomLine = lineIndex.get(
              station.lineIds[station.lineIds.length - 1],
            )!;
            const primaryColor = colorFor(station.primary);
            return (
              <g
                key={station.project.id}
                data-kind="project"
                data-id={station.project.id}
                opacity={stationOpacity(station)}
                className={drag?.id === station.project.id ? "cursor-grabbing" : "cursor-grab"}
                role="button"
                tabIndex={0}
                aria-label={`${station.project.label} station`}
                onClick={() =>
                  setActive((current) =>
                    current === station.project.id ? null : station.project.id,
                  )
                }
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    setActive((current) =>
                      current === station.project.id ? null : station.project.id,
                    );
                  }
                }}
                onMouseEnter={() => setHovered(station.project.id)}
                onMouseLeave={() => setHovered(null)}
                onPointerDown={(e) => onPointerDown(station, e)}
                onPointerMove={onPointerMove}
                onPointerUp={onPointerUp}
              >
                <title>{tooltipFor(station.project)}</title>
                {station.lineIds.length > 1 && (
                  <line
                    x1={station.x}
                    x2={station.x}
                    y1={TOP + topLine * ROW_GAP}
                    y2={TOP + bottomLine * ROW_GAP}
                    stroke={primaryColor}
                    strokeWidth={1.5}
                    opacity={0.45}
                  />
                )}
                {station.lineIds.map((lineId) => (
                  <circle
                    key={lineId}
                    cx={station.x}
                    cy={TOP + lineIndex.get(lineId)! * ROW_GAP}
                    r={6}
                    fill="#1e1e1e"
                    stroke={colorFor(lineId)}
                    strokeWidth={2}
                    data-platform={lineId}
                  />
                ))}
                <text
                  x={station.x - 12}
                  y={TOP + topLine * ROW_GAP + 4}
                  textAnchor="end"
                  paintOrder="stroke"
                  stroke="#0a0a0a"
                  strokeWidth={3.5}
                  className="fill-slate-300 text-[12px]"
                >
                  <title>{station.project.label}</title>
                  {station.project.label}
                </text>
              </g>
            );
          })}
        </svg>
        <div className="mt-1 flex min-h-7 flex-wrap items-center gap-x-4 gap-y-1 text-xs text-neutral-400">
          <span className="flex items-center gap-1.5">
            <span className="h-0.5 w-6 rounded bg-amber-500" /> Shared technology
            (line)
          </span>
          <span className="flex items-center gap-1.5">
            <span className="h-3 w-3 rounded-full border-2 border-amber-500 bg-neutral-800" />
            Project (station)
          </span>
          <span className="text-neutral-500">
            Hover or click to focus · drag stations · click a line to reverse-focus
          </span>
          {(active || layoutDirty) && (
            <button
              onClick={resetLayout}
              className="rounded border border-neutral-700 px-1.5 py-0.5 text-neutral-400 hover:text-neutral-200"
            >
              Reset layout
            </button>
          )}
        </div>
        {unserved.length > 0 && (
          <div className="mt-2 flex flex-wrap items-center gap-1.5 text-xs">
            <span className="text-neutral-500">
              Unserved ({unserved.length} — no shared techs in the visible lines):
            </span>
            {unserved.map((p) => (
              <button
                key={p.id}
                data-unserved={p.id}
                onClick={() =>
                  setActive((current) => (current === p.id ? null : p.id))
                }
                className="rounded-full border border-neutral-700 px-2 py-0.5 text-neutral-400 hover:border-neutral-500 hover:text-neutral-200"
              >
                {p.label}
              </button>
            ))}
          </div>
        )}
        <details className="text-xs text-neutral-400">
          <summary className="cursor-pointer hover:text-neutral-200">All technologies ({techList.length})</summary>
          <ul data-testid="galaxy-tech-list" className="mt-1 space-y-0.5">
            {techList.map((n) => (
              <li key={n.id}>
                <span className="text-amber-400">{n.label}</span> — {n.detail}
              </li>
            ))}
          </ul>
        </details>
      </div>
      <FocusPanel
        node={focusNode}
        nodesById={nodesById}
        linkedTechs={linkedTechs}
        linkedProjects={linkedProjects}
        onClose={() => setActive(null)}
      />
    </div>
  );
}

function defaultPositions(graph: GalaxyGraph): Map<string, number> {
  const map = new Map<string, number>();
  const techs = graph.nodes
    .filter((n) => n.kind === "tech")
    .sort((a, b) => usageCount(b.detail) - usageCount(a.detail));
  const lineIndex = new Map(techs.map((t, i) => [t.id, i]));
  const techLinks = new Map<string, Set<string>>();
  for (const link of graph.links) {
    if (!techLinks.has(link.source)) techLinks.set(link.source, new Set());
    if (!techLinks.has(link.target)) techLinks.set(link.target, new Set());
    techLinks.get(link.source)!.add(link.target);
    techLinks.get(link.target)!.add(link.source);
  }
  const served = graph.nodes
    .filter((n) => n.kind === "project")
    .map((p) => ({
      p,
      lineIds: [...(techLinks.get(p.id) ?? [])].filter((id) => lineIndex.has(id)),
    }))
    .filter((x) => x.lineIds.length > 0)
    .sort((a, b) => {
      const ai = Math.min(...a.lineIds.map((id) => lineIndex.get(id)!));
      const bi = Math.min(...b.lineIds.map((id) => lineIndex.get(id)!));
      return ai !== bi ? ai - bi : a.p.label.localeCompare(b.p.label);
    });
  served.forEach((x, i) => map.set(x.p.id, MARGIN_X + i * SLOT_STEP));
  return map;
}