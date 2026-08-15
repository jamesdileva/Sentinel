import { useState } from "react"
import ArchitectureMap from "../components/ArchitectureMap"
import ClusterView from "../components/ClusterView"
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
  const [galaxyView, setGalaxyView] = useState<"metro" | "families">("metro")
  return (
    <div className="space-y-10">
      <header>
        <h1 className="text-2xl font-bold text-neutral-100">Observatory</h1>
        <p className="text-neutral-500">Deterministic overviews of your indexed projects — no AI involved.</p>
      </header>
      <Section title="Project Galaxy" subtitle="Technologies shared by two or more projects">
        <div className="flex items-center gap-2">
          <div className="flex rounded-lg border border-neutral-700 p-0.5 text-xs">
            <button
              onClick={() => setGalaxyView("metro")}
              className={`rounded-md px-3 py-1 ${galaxyView === "metro" ? "bg-neutral-700 text-white" : "text-neutral-400 hover:text-neutral-200"}`}
            >
              Metro
            </button>
            <button
              onClick={() => setGalaxyView("families")}
              className={`rounded-md px-3 py-1 ${galaxyView === "families" ? "bg-neutral-700 text-white" : "text-neutral-400 hover:text-neutral-200"}`}
            >
              Families
            </button>
          </div>
          <p className="text-xs text-neutral-500">
            {galaxyView === "metro"
              ? "Shared techs as transit lines; projects as stations where lines meet."
              : "Projects clustered by tech similarity into a family tree + usage matrix."}
          </p>
        </div>
        {galaxyView === "metro" ? <MetroView /> : <ClusterView />}
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