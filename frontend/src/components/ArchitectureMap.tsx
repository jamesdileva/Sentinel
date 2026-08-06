import { useEffect, useState } from "react"
import type { ArchitectureNode, Project } from "../types"
import { getArchitecture } from "../api/observatory"
import { listProjects } from "../api/projects"

function Node({ node, depth }: { node: ArchitectureNode; depth: number }) {
  const indent = { paddingLeft: `${depth * 14}px` }
  if (node.children.length === 0) {
    return (
      <div style={indent} className="text-xs text-neutral-400">
        <span>─ </span>
        <span className="text-neutral-200">{node.name}</span>
      </div>
    )
  }
  return (
    <div>
      <div style={indent} className="text-xs font-medium text-amber-300">
        ▸ {node.name} <span className="font-normal text-neutral-500">({node.count})</span>
      </div>
      {node.children.map((child) => (
        <Node key={child.path} node={child} depth={depth + 1} />
      ))}
    </div>
  )
}

export default function ArchitectureMap() {
  const [projects, setProjects] = useState<Project[]>([])
  const [selected, setSelected] = useState<string>("")
  const [tree, setTree] = useState<ArchitectureNode | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    listProjects()
      .then((response) => {
        setProjects(response.projects)
        if (response.projects.length > 0) setSelected(response.projects[0].id)
      })
      .catch((e) => setError(String(e)))
  }, [])

  useEffect(() => {
    if (!selected) return
    setTree(null)
    getArchitecture(selected)
      .then(setTree)
      .catch((e) => setError(String(e)))
  }, [selected])

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
      {tree && (
        <div className="rounded-lg border border-neutral-800 bg-neutral-900/60 p-3">
          <Node node={tree} depth={0} />
        </div>
      )}
    </div>
  )
}