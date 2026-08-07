import { useEffect, useState } from "react";

import {
  getSystemOverview,
  type SystemOverview as SystemOverviewData,
} from "../api/system";

export default function System() {
  const [data, setData] = useState<SystemOverviewData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const report = await getSystemOverview();
        if (cancelled) return;
        setData(report);
        setError(null);
      } catch (err) {
        if (!cancelled) {
          setError(
            err instanceof Error ? err.message : "Cannot load system status.",
          );
        }
      }
    };
    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <section aria-label="Home server status" className="flex flex-col gap-4">
      <div className="rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
        <h2 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
          Home Server
        </h2>
        <p className="text-xs text-slate-400 dark:text-slate-500">
          Read-only status of the always-on machine: AI (Ollama) and network
          filtering (Pi-hole).
        </p>
        {error && (
          <div className="mt-3 rounded-lg border border-red-300 bg-red-50 px-4 py-2 text-sm text-red-800 dark:border-red-800 dark:bg-red-950 dark:text-red-200">
            {error}
          </div>
        )}
      </div>

      {data ? (
        <>
          <OllamaPanel ollama={data.ollama} />
          <PiHolePanel pihole={data.pihole} />
          <StartupPanel states={data.startup.states} />
        </>
      ) : (
        !error && (
          <div className="rounded-xl border border-dashed border-slate-300 p-4 text-center text-sm text-slate-400 dark:border-slate-700 dark:text-slate-500">
            Loading…
          </div>
        )
      )}
    </section>
  );
}

function Badge({ ok, label }: { ok: boolean; label: string }) {
  return (
    <span
      className={`inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs font-medium ${
        ok
          ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-500/15 dark:text-emerald-300"
          : "bg-red-100 text-red-800 dark:bg-red-500/15 dark:text-red-300"
      }`}
    >
      <span
        className={`h-2 w-2 rounded-full ${ok ? "bg-emerald-500" : "bg-red-500"}`}
        aria-hidden="true"
      />
      {label}
    </span>
  );
}

function OllamaPanel({ ollama }: { ollama: SystemOverviewData["ollama"] }) {
  const recent = ollama.recent ?? [];
  const withTps = recent.filter((r) => r.tokens_per_second !== null);
  const avgTps =
    withTps.length === 0
      ? null
      : withTps.reduce((sum, r) => sum + (r.tokens_per_second ?? 0), 0) /
        withTps.length;

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
      <div className="flex items-center justify-between gap-3">
        <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
          Ollama (AI)
        </h3>
        <Badge
          ok={ollama.available}
          label={ollama.available ? "reachable" : "offline"}
        />
      </div>
      <p className="mt-1 break-all text-xs text-slate-400 dark:text-slate-500">
        {ollama.host} · default model {ollama.model_default}
      </p>

      {ollama.models.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-2">
          {ollama.models.map((model) => (
            <span
              key={model}
              className="rounded-md border border-slate-200 bg-slate-50 px-2 py-1 text-xs text-slate-700 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300"
            >
              {model}
            </span>
          ))}
        </div>
      )}

      <div className="mt-4">
        <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
          Recent generations
          {avgTps !== null && (
            <span className="ml-2 normal-case text-emerald-600 dark:text-emerald-400">
              avg {avgTps.toFixed(1)} t/s
            </span>
          )}
        </h4>
        {recent.length === 0 ? (
          <p className="mt-2 text-center text-sm text-slate-400 dark:text-slate-500">
            No generations recorded yet. Ask the RAG assistant to see throughput
            here.
          </p>
        ) : (
          <ul className="mt-2 flex flex-col gap-2">
            {recent.map((record) => (
              <li
                key={`${record.created_at}-${record.model}`}
                className="flex items-center justify-between gap-3 rounded-lg border border-slate-100 bg-slate-50 px-3 py-2 text-xs dark:border-slate-800 dark:bg-slate-900"
              >
                <span className="truncate text-slate-700 dark:text-slate-300">
                  {record.model} · {record.eval_count} tokens
                </span>
                <span className="whitespace-nowrap text-slate-400 dark:text-slate-500">
                  {record.tokens_per_second !== null
                    ? `${record.tokens_per_second.toFixed(1)} t/s`
                    : "—"}{" "}
                  · {record.latency_ms} ms
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

function PiHolePanel({ pihole }: { pihole: SystemOverviewData["pihole"] }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
      <div className="flex items-center justify-between gap-3">
        <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
          Pi-hole
        </h3>
        <Badge
          ok={pihole.configured && pihole.blocking === "enabled"}
          label={
            pihole.error
              ? "error"
              : pihole.blocking === "enabled"
                ? "blocking"
                : pihole.blocking === "disabled"
                  ? "disabled"
                  : "not configured"
          }
        />
      </div>
      <p className="mt-1 break-all text-xs text-slate-400 dark:text-slate-500">
        {pihole.configured
          ? pihole.host
          : (pihole.error ?? "Configure via .env")}
      </p>

      {pihole.queries_total !== null && (
        <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-3">
          {[
            {
              label: "Queries today",
              value: Number(pihole.queries_total).toLocaleString(),
            },
            {
              label: "Blocked today",
              value: Number(pihole.queries_blocked ?? 0).toLocaleString(),
            },
            {
              label: "Blocked %",
              value: `${pihole.blocked_percent ?? 0}%`,
            },
          ].map((stat) => (
            <div
              key={stat.label}
              className="rounded-lg border border-slate-100 bg-slate-50 px-3 py-2 dark:border-slate-800 dark:bg-slate-900"
            >
              <p className="text-xs text-slate-400 dark:text-slate-500">
                {stat.label}
              </p>
              <p className="mt-1 text-lg font-semibold text-slate-900 dark:text-slate-100">
                {stat.value}
              </p>
            </div>
          ))}
        </div>
      )}

      {pihole.clients !== null && (
        <p className="mt-3 text-xs text-slate-400 dark:text-slate-500">
          Active clients: {pihole.clients}
        </p>
      )}
    </div>
  );
}

function StartupPanel({
  states,
}: {
  states: SystemOverviewData["startup"]["states"];
}) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
      <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
        Startup checks
      </h3>
      <ul className="mt-3 flex flex-col gap-2">
        {states.map((state) => (
          <li
            key={state.name}
            className="flex items-center justify-between gap-3 text-sm"
          >
            <span className="capitalize text-slate-700 dark:text-slate-300">
              {state.name}
            </span>
            <span
              className={`truncate text-xs ${
                state.ok
                  ? "text-emerald-600 dark:text-emerald-400"
                  : "text-red-600 dark:text-red-400"
              }`}
              title={state.detail}
            >
              {state.ok ? "ok" : state.detail}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
