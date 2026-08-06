import ArchitectureMap from "../components/ArchitectureMap"
import ProjectGalaxy from "../components/ProjectGalaxy"
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
  return (
    <div className="space-y-10">
      <header>
        <h1 className="text-2xl font-bold text-neutral-100">Observatory</h1>
        <p className="text-neutral-500">Deterministic overviews of your indexed projects — no AI involved.</p>
      </header>
      <Section title="Project Galaxy" subtitle="Technologies shared by two or more projects">
        <ProjectGalaxy />
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