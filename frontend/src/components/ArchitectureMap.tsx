import { useEffect, useMemo, useState } from "react";
import type { ArchitectureNode, Project } from "../types";
import { getArchitecture } from "../api/observatory";
import { listProjects } from "../api/projects";

const FILE_COLORS: Record<string, string> = {
  ".py": "text-amber-300",
  ".ts": "text-sky-300",
  ".tsx": "text-sky-300",
  ".js": "text-sky-300",
  ".jsx": "text-sky-300",
  ".md": "text-neutral-300",
  ".json": "text-neutral-500",
  ".cpp": "text-rose-300",
  ".c": "text-rose-300",
  ".h": "text-rose-300",
  ".rs": "text-orange-300",
  ".go": "text-cyan-300",
  ".toml": "text-neutral-400",
  ".yml": "text-neutral-400",
  ".yaml": "text-neutral-400",
  ".html": "text-orange-300",
  ".css": "text-violet-300",
};

function fileColor(name: string): string {
  const dot = name.lastIndexOf(".");
  if (dot < 0) return "text-neutral-400";
  return FILE_COLORS[name.slice(dot).toLowerCase()] ?? "text-neutral-400";
}

function countDirs(node: ArchitectureNode): number {
  const dirs = node.children.length > 0 ? 1 : 0;
  return dirs + node.children.reduce((sum, child) => sum + countDirs(child), 0);
}

function filterTree(node: ArchitectureNode, term: string): ArchitectureNode | null {
  const selfMatch = node.path.toLowerCase().includes(term.toLowerCase());
  const children = node.children
    .map((child) => filterTree(child, term))
    .filter((child): child is ArchitectureNode => child !== null);
  if (!selfMatch && children.length === 0) return null;
  return { ...node, children };
}

function Node({
  node,
  depth,
  collapsed,
  onToggle,
}: {
  node: ArchitectureNode;
  depth: number;
  collapsed: Set<string>;
  onToggle: (path: string) => void;
}) {
  const indent = { paddingLeft: `${depth * 14}px` };
  const isDir = node.children.length > 0;
  if (!isDir) {
    return (
      <div style={indent} className="text-xs">
        <span>─ </span>
        <span className={fileColor(node.name)}>{node.name}</span>
      </div>
    );
  }
  const isCollapsed = collapsed.has(node.path);
  return (
    <div>
      <button
        type="button"
        onClick={() => onToggle(node.path)}
        style={indent}
        className="text-xs font-medium text-amber-300 hover:text-amber-200"
      >
        <span className={isCollapsed ? "" : "inline-block rotate-90"}>▸</span>{" "}
        {node.name} <span className="font-normal text-neutral-500">({node.count})</span>
      </button>
      {!isCollapsed &&
        node.children.map((child) => (
          <Node
            key={child.path}
            node={child}
            depth={depth + 1}
            collapsed={collapsed}
            onToggle={onToggle}
          />
        ))}
    </div>
  );
}

export default function ArchitectureMap() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [selected, setSelected] = useState<string>("");
  const [tree, setTree] = useState<ArchitectureNode | null>(null);
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());
  const [term, setTerm] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // v1.17.18.3 (audit2 Q9): clear the latch before each attempt so one
    // transient failure no longer bricks the panel until a page reload.
    setError(null);
    listProjects()
      .then((response) => {
        setProjects(response.projects);
        if (response.projects.length > 0) setSelected(response.projects[0].id);
      })
      .catch((e) => setError(String(e)));
  }, []);

  useEffect(() => {
    if (!selected) return;
    setTree(null);
    setCollapsed(new Set());
    setTerm("");
    setError(null);
    getArchitecture(selected)
      .then(setTree)
      .catch((e) => setError(String(e)));
  }, [selected]);

  const toggle = (path: string) => {
    setCollapsed((current) => {
      const next = new Set(current);
      if (next.has(path)) next.delete(path);
      else next.add(path);
      return next;
    });
  };

  const visible = useMemo(() => {
    if (!tree) return null;
    return term ? filterTree(tree, term) : tree;
  }, [tree, term]);

  const stats = useMemo(() => {
    if (!tree) return null;
    const dirs = countDirs(tree) - 1; // root itself is a dir
    const topLevel = tree.children
      .filter((child) => child.children.length > 0)
      .slice(0, 8);
    return { files: tree.count, dirs, topLevel };
  }, [tree]);

  return (
    <div className="space-y-4">
      <label className="flex items-center gap-2 text-sm text-neutral-400">
        <span>Project</span>
        <select
          value={selected}
          onChange={(e) => setSelected(e.target.value)}
          className="rounded bg-neutral-800 px-2 py-1 text-sm text-neutral-100"
        >
          {projects.map((project) => (
            <option key={project.id} value={project.id}>
              {project.name}
            </option>
          ))}
        </select>
      </label>
      {error && <p className="text-red-500 text-sm">Architecture failed to load: {error}</p>}
      {!error && !tree && <p className="text-sm text-neutral-500">Loading architecture…</p>}
      {!error && stats && tree && (
        <div className="flex flex-wrap items-center gap-2">
          <span className="rounded bg-neutral-800 px-2 py-0.5 text-xs text-neutral-300">
            {stats.files} files
          </span>
          <span className="rounded bg-neutral-800 px-2 py-0.5 text-xs text-neutral-300">
            {stats.dirs} dirs
          </span>
          {stats.topLevel.map((child) => (
            <span
              key={child.path}
              className="rounded bg-neutral-900 px-2 py-0.5 text-xs text-amber-300/80"
              title={`${child.count} files under ${child.name}`}
            >
              {child.name} · {child.count}
            </span>
          ))}
        </div>
      )}
      {!error && tree && (
        <div className="space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <input
              type="search"
              value={term}
              onChange={(e) => setTerm(e.target.value)}
              placeholder="Filter files…"
              className="w-48 rounded bg-neutral-800 px-2 py-1 text-sm text-neutral-100 placeholder:text-neutral-500"
            />
            <button
              type="button"
              onClick={() =>
                setCollapsed((current) =>
                  current.size === 0 && tree.children.length > 0
                    ? new Set(collectPaths(tree))
                    : new Set(),
                )
              }
              className="rounded bg-neutral-800 px-2 py-1 text-xs text-neutral-300 hover:bg-neutral-700"
            >
              {collapsed.size === 0 ? "Collapse all" : "Expand all"}
            </button>
          </div>
          {visible && (
            <div className="rounded-lg border border-neutral-800 bg-neutral-900/60 p-3">
              <Node node={visible} depth={0} collapsed={collapsed} onToggle={toggle} />
            </div>
          )}
          {!visible && (
            <p className="text-sm text-neutral-500">No files match “{term}”.</p>
          )}
        </div>
      )}
    </div>
  );
}

function collectPaths(node: ArchitectureNode): string[] {
  const dirs = node.children.length > 0 ? [node.path] : [];
  for (const child of node.children) dirs.push(...collectPaths(child));
  return dirs;
}