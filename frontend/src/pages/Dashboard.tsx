const STATS = [
  { label: "Projects", value: "0", hint: "Indexed repositories" },
  { label: "Builds", value: "0", hint: "Last 7 days" },
  { label: "Findings", value: "0", hint: "Open security issues" },
  { label: "Health", value: "—", hint: "Average score" },
] as const;

export default function Dashboard() {
  return (
    <section aria-label="Dashboard overview">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {STATS.map((stat) => (
          <div
            key={stat.label}
            className="rounded-xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900"
          >
            <p className="text-sm text-slate-500 dark:text-slate-400">{stat.label}</p>
            <p className="mt-2 text-3xl font-semibold tracking-tight text-slate-900 dark:text-slate-100">
              {stat.value}
            </p>
            <p className="mt-1 text-xs text-slate-400 dark:text-slate-500">{stat.hint}</p>
          </div>
        ))}
      </div>

      <div className="mt-6 rounded-xl border border-dashed border-slate-300 p-8 text-center dark:border-slate-700">
        <p className="text-sm text-slate-500 dark:text-slate-400">
          Project Sentinel dashboard scaffolding is live.
        </p>
        <p className="mt-1 text-xs text-slate-400 dark:text-slate-500">
          Live project stats arrive with the API client in Sprint 6.
        </p>
      </div>
    </section>
  );
}
