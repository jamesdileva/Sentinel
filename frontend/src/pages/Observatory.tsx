import { useEffect, useState } from "react"
import type { GalaxyGraph } from "../types"
import { getGalaxy } from "../api/observatory"
import ArchitectureMap from "../components/ArchitectureMap"
import GalaxyView from "../components/GalaxyView"
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
  // v1.17.18.6: the force-directed Galaxy is the only project-graph view —
  // metro/families were retired (git history keeps them if ever wanted).
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
      <Section
        title="Project Galaxy"
        subtitle="Force-directed map — projects cluster around the technologies they share."
      >
        {graphError ? (
          <p className="text-sm text-red-500">Galaxy failed to load: {graphError}</p>
        ) : !graph ? (
          <p className="text-sm text-neutral-500">Loading galaxy…</p>
        ) : (
          <GalaxyView graph={graph} />
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