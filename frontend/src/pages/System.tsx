import ServerStatus from "../components/ServerStatus";

/**
 * Settings page (v1.17.3): the Ollama + startup-check panels moved to the
 * Dashboard; this tab is the future home for configuration — sync interval,
 * watch dirs, automatic GitHub token retrieval (deferred, see docs/later.md).
 * The read-only server status still renders here so nothing regresses.
 */
export default function System() {
  return (
    <section aria-label="Settings" className="flex flex-col gap-4">
      <div className="rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
        <h2 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
          Settings
        </h2>
        <p className="text-xs text-slate-400 dark:text-slate-500">
          Server configuration is coming soon — sync interval, watch dirs and
          GitHub token retrieval (deferred feature list in docs/later.md).
        </p>
      </div>

      <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
        Home server
      </h3>
      <ServerStatus />
    </section>
  );
}