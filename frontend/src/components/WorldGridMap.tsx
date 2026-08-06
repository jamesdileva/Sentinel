import { useEffect, useRef } from "react";

import type { WorldRoad, WorldSettlement } from "../api/world_sim";

// Deterministic terrain — mirrors app/services/world_sim/rules_engine.py.
// BigInt arithmetic keeps the 32-bit masking identical to Python's.
function hashCell(x: number, y: number, seed: number): number {
  let h = BigInt.asUintN(
    32,
    BigInt(x) * 374761393n +
      BigInt(y) * 668265263n +
      BigInt(seed) * 1274126177n,
  );
  h = BigInt.asUintN(32, (h ^ (h >> 13n)) * 1274126177n);
  h = BigInt.asUintN(32, h ^ (h >> 16n));
  return Number(h);
}

export function terrainAt(x: number, y: number, seed: number): string {
  const r = hashCell(x, y, seed) / 0xffffffff;
  if (r < 0.1) return "mountains";
  if (r < 0.24) return "water";
  if (r < 0.44) return "hills";
  if (r < 0.72) return "forest";
  return "plains";
}

const TERRAIN_COLORS: Record<string, string> = {
  mountains: "#7c8494",
  water: "#4a9fd1",
  hills: "#d9a349",
  forest: "#4f8f62",
  plains: "#9cbf8a",
};

const PADDING = 2;

interface Props {
  settlements: WorldSettlement[];
  roads: WorldRoad[];
  seed: number;
  selectedId: string | null;
  onSelect: (id: string | null) => void;
}

function bounds(settlements: WorldSettlement[], width: number) {
  if (settlements.length === 0) {
    return { minX: 8, minY: 8, maxX: 30, maxY: 24, cell: 24 };
  }
  const xs = settlements.map((s) => s.x);
  const ys = settlements.map((s) => s.y);
  const minX = Math.min(...xs) - PADDING;
  const maxX = Math.max(...xs) + PADDING;
  const minY = Math.min(...ys) - PADDING;
  const maxY = Math.max(...ys) + PADDING;
  const cols = maxX - minX + 1;
  const cell = Math.min(26, Math.floor(width / Math.max(cols, 8)));
  return { minX, minY, maxX, maxY, cell };
}

export default function WorldGridMap({
  settlements,
  roads,
  seed,
  selectedId,
  onSelect,
}: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const latest = useRef({ settlements, roads, seed, selectedId, onSelect });
  latest.current = { settlements, roads, seed, selectedId, onSelect };

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    const { settlements, roads, seed, selectedId } = latest.current;

    const width = canvas.clientWidth || 640;
    const { minX, minY, maxX, maxY, cell } = bounds(settlements, width);
    canvas.width = width;
    canvas.height = (maxY - minY + 1) * cell;
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    const byId = new Map(settlements.map((s) => [s.id, s]));
    const drawX = (x: number) => (x - minX) * cell + cell / 2;
    const drawY = (y: number) => (y - minY) * cell + cell / 2;

    // Terrain backdrop.
    for (let gy = minY; gy <= maxY; gy += 1) {
      for (let gx = minX; gx <= maxX; gx += 1) {
        ctx.fillStyle = TERRAIN_COLORS[terrainAt(gx, gy, seed)] ?? "#94a3b8";
        ctx.fillRect((gx - minX) * cell, (gy - minY) * cell, cell, cell);
        ctx.strokeStyle = "rgba(0,0,0,0.05)";
        ctx.strokeRect((gx - minX) * cell, (gy - minY) * cell, cell, cell);
      }
    }

    // Roads connect settlement centers.
    ctx.lineWidth = 3;
    ctx.strokeStyle = "rgba(255,255,255,0.55)";
    for (const road of roads) {
      const a = byId.get(road.from_id);
      const b = byId.get(road.to_id);
      if (!a || !b) continue;
      ctx.beginPath();
      ctx.moveTo(drawX(a.x), drawY(a.y));
      ctx.lineTo(drawX(b.x), drawY(b.y));
      ctx.stroke();
    }

    // Settlements as dots sized by population.
    for (const s of settlements) {
      const x = drawX(s.x);
      const y = drawY(s.y);
      const radius =
        4 + Math.min(9, Math.round(Math.sqrt(Math.max(s.population, 0)) / 4));
      ctx.beginPath();
      ctx.arc(x, y, radius, 0, Math.PI * 2);
      ctx.fillStyle =
        s.status === "abandoned"
          ? "#94a3b8"
          : s.id === selectedId
            ? "#e11d48"
            : "#4f46e5";
      ctx.fill();
      ctx.lineWidth = 2;
      ctx.strokeStyle = "rgba(255,255,255,0.9)";
      ctx.stroke();
    }
  }, [settlements, roads, seed, selectedId]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const handleClick = (event: MouseEvent) => {
      const { settlements, onSelect } = latest.current;
      const rect = canvas.getBoundingClientRect();
      const px = (event.clientX - rect.left) * (canvas.width / rect.width);
      const py = (event.clientY - rect.top) * (canvas.height / rect.height);
      if (settlements.length === 0) {
        onSelect(null);
        return;
      }
      const { minX, minY, cell } = bounds(settlements, canvas.width);
      const drawX = (x: number) => (x - minX) * cell + cell / 2;
      const drawY = (y: number) => (y - minY) * cell + cell / 2;
      let best: string | null = null;
      let bestDist = Math.max(cell * 1.4, 16);
      for (const s of settlements) {
        const dx = px - drawX(s.x);
        const dy = py - drawY(s.y);
        const dist = Math.hypot(dx, dy);
        if (dist < bestDist) {
          best = s.id;
          bestDist = dist;
        }
      }
      onSelect(best);
    };
    canvas.addEventListener("pointerdown", handleClick);
    return () => canvas.removeEventListener("pointerdown", handleClick);
  }, []);

  return (
    <canvas
      ref={canvasRef}
      className="w-full rounded-xl border border-slate-200 dark:border-slate-800"
      style={{ minHeight: 300 }}
      aria-label="World map"
    />
  );
}
