import type { GalaxyNode } from "../types";
import { usageCount } from "./galaxyShared";

/**
 * Side panel describing the focused project or tech. Rendered at a fixed
 * width on every layout (invisible when nothing is focused) so the graph
 * never reflows — v1.17.9.2 flicker fix.
 */
export default function FocusPanel({
  node,
  nodesById,
  linkedTechs,
  linkedProjects,
  onClose,
}: {
  node: GalaxyNode | undefined;
  nodesById: Map<string, GalaxyNode>;
  linkedTechs: (projectId: string) => Set<string>;
  linkedProjects: (techId: string) => Set<string>;
  onClose: () => void;
}) {
  if (!node)
    return (
      <aside className="invisible w-64 shrink-0" aria-hidden="true">
        <div className="h-40 rounded border border-neutral-800 bg-neutral-900" />
      </aside>
    );

  const list = (
    node.kind === "project"
      ? [...linkedTechs(node.id)]
          .map((id) => nodesById.get(id))
          .filter((n): n is GalaxyNode => Boolean(n))
          .sort((a, b) => usageCount(b.detail) - usageCount(a.detail))
      : [...linkedProjects(node.id)]
          .map((id) => nodesById.get(id))
          .filter((n): n is GalaxyNode => Boolean(n))
          .sort((a, b) => a.label.localeCompare(b.label))
  );

  return (
    <aside className="w-64 shrink-0 rounded border border-neutral-800 bg-neutral-900 p-3 text-xs">
      <div className="flex items-start justify-between gap-2">
        <div>
          <h3 className="text-base font-semibold text-white">{node.label}</h3>
          {node.kind === "project" ? (
            <p className="mt-0.5 text-neutral-400">
              {[node.detail, node.framework].filter(Boolean).join(" · ") ||
                "no metadata"}
            </p>
          ) : (
            <p className="mt-0.5 text-neutral-400">{node.detail}</p>
          )}
        </div>
        <button
          onClick={onClose}
          className="text-neutral-500 hover:text-neutral-300"
          aria-label="Clear focus"
        >
          ×
        </button>
      </div>
      <div className="mt-3">
        <p className="font-medium text-neutral-300">
          {node.kind === "project" ? "Shared technologies" : "Used by"}
        </p>
        <ul className="mt-1 space-y-1 text-neutral-400">
          {list.map((n) => (
            <li key={n.id}>
              <span className="text-amber-400">{n.label}</span>
              {n.detail && ` — ${n.detail}`}
            </li>
          ))}
        </ul>
      </div>
    </aside>
  );
}