import { useEffect, useState } from "react"
import type { GalaxyGraph } from "../types"
import { getGalaxy } from "../api/observatory"
import ArchitectureMap from "../components/ArchitectureMap"
import ClusterView from "../components/ClusterView"
import GalaxyView from "../components/GalaxyView"
import MetroView from "../components/MetroView"
import ProjectTimeline from "../components/ProjectTimeline"

function Section({ title, subtitle, children }: { title: string; subtitle: string; children: React.ReactNode }) {
  return (
    <section className="space-y-3">
      <div>
        <h2 className="text-lg font-semibold text-neutral-100">{title}</h2>
        <p className="text-sm text-neutral-500">{subtitle}</p>
      </div>
      {children}
    </section>
  )
}

export default function Observatory() {
  // v1.17.18.6: force-directed Galaxy is the primary view; metro/families
  // stay as secondary tabs pending a decision on their retirement.
  const [galaxyView, setGalaxyView] = useState<"galaxy" | "metro" | "families">("galaxy")
  const [graph, setGraph] = useState<GalaxyGraph | null>(null)
  const [graphError, setGraphError] = useState<string | null>(null)

  useEffect(() => {
    getGalaxy()
      .then(setGraph)
      .catch((e) => setGraphError(String(e)))
  }, [])

  return (
    <div className="space-y-10">
      <header>
        <h1 className="text-2xl font-bold text-neutral-100">Observatory</h1>
        <p className="text-neutral-500">Deterministic overviews of your indexed projects — no AI involved.</p>
      </header>
      <Section title="Project Galaxy" subtitle="Technologies shared by two or more projects">
        <div className="flex items-center gap-2">
          <div className="flex rounded-lg border border-neutral-700 p-0.5 text-xs">
            {(
              [
                ["galaxy", "Galaxy"],
                ["metro", "Metro"],
                ["families", "Families"],
              ] as const
            ).map(([key, label]) => (
              <button
                key={key}
                onClick={() => setGalaxyView(key)}
                data-active={galaxyView === key}
                className={`rounded-md px-3 py-1 ${galaxyView === key ? "bg-neutral-700 text-white" : "text-neutral-400 hover:text-neutral-200"}`}
              >
                {label}
              </button>
            ))}
          </div>
          <p className="text-xs text-neutral-500">
            {galaxyView === "galaxy"
              ? "Force-directed map — projects cluster around the technologies they share."
              : galaxyView === "metro"
                ? "Shared techs as transit lines; projects as stations where lines meet."
                : "Projects clustered by tech similarity into a family tree + usage matrix."}
          </p>
        </div>
        {graphError ? (
          <p className="text-sm text-red-500">Galaxy failed to load: {graphError}</p>
        ) : !graph ? (
          <p className="text-sm text-neutral-500">Loading galaxy…</p>
        ) : galaxyView === "galaxy" ? (
          <GalaxyView graph={graph} />
        ) : galaxyView === "metro" ? (
          <MetroView graph={graph} />
        ) : (
          <ClusterView graph={graph} />
        )}
      </Section>
      <Section title="Activity Timeline" subtitle="Recent commits, builds, test runs, and security findings.">
        <ProjectTimeline />
      </Section>
      <Section title="Architecture Map" subtitle="Component tree derived from indexed file paths.">
        <ArchitectureMap />
      </Section>
    </div>
  )
}