import { useEffect, useMemo, useState } from "react";

import {
  accelerateWorld,
  getWorldState,
  resetWorld,
  tickWorld,
  triggerWorldDisaster,
  type WorldState,
  type WorldSettlement,
} from "../api/world_sim";
import WorldGridMap from "../components/WorldGridMap";
import { useUI } from "../contexts/UIContext";

const DISASTERS = ["flood", "drought", "plague"];
const POLL_MS = 3000;

export default function WorldSimulatorPage() {
  const { toast } = useUI();
  const [state, setState] = useState<WorldState | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [disasterType, setDisasterType] = useState("flood");
  const [seedInput, setSeedInput] = useState("");

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const fresh = await getWorldState();
        if (!cancelled) {
          setState(fresh);
          setError(null);
        }
      } catch (err) {
        if (!cancelled) {
          setError(
            err instanceof Error ? err.message : "Cannot load the world.",
          );
        }
      }
    };
    void load();
    const timer = setInterval(() => void load(), POLL_MS);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, []);

  const selected = useMemo(
    () => state?.settlements.find((s) => s.id === selectedId) ?? null,
    [state, selectedId],
  );

  async function refresh() {
    try {
      setState(await getWorldState());
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Cannot load the world.");
    }
  }

  async function run(action: () => Promise<unknown>, message: string) {
    if (busy) return;
    setBusy(true);
    try {
      await action();
      toast(message, "success");
      await refresh();
    } catch (err) {
      toast(err instanceof Error ? err.message : "Action failed.", "error");
    } finally {
      setBusy(false);
    }
  }

  function handleDisaster(settlementId: string | null) {
    if (!settlementId) {
      toast("Select a settlement on the map first.", "error");
      return;
    }
    void run(
      () => triggerWorldDisaster(settlementId, disasterType),
      `A ${disasterType} struck!`,
    );
  }

  const stats = state?.stats;
  const active = state?.settlements.filter((s) => s.status === "active") ?? [];

  return (
    <section aria-label="World simulator" className="flex flex-col gap-4">
      <div className="rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h2 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
              The Living World
            </h2>
            <p className="text-xs text-slate-400 dark:text-slate-500">
              Day {state?.day_number ?? 0} · seed {state?.seed ?? "…"} ·{" "}
              {state ? `${state.time_scale} day(s) per tick` : "waiting"}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2 text-xs">
            <button
              type="button"
              onClick={() => void run(() => tickWorld(1), "Advanced 1 day.")}
              disabled={busy}
              className="rounded-lg bg-slate-800 px-3 py-1.5 text-white hover:bg-slate-700 disabled:opacity-50 dark:bg-slate-200 dark:text-slate-900"
            >
              +1 day
            </button>
            <button
              type="button"
              onClick={() => void run(() => tickWorld(10), "Advanced 10 days.")}
              disabled={busy}
              className="rounded-lg bg-slate-800 px-3 py-1.5 text-white hover:bg-slate-700 disabled:opacity-50 dark:bg-slate-200 dark:text-slate-900"
            >
              +10 days
            </button>
            <button
              type="button"
              onClick={() => void run(() => tickWorld(30), "Advanced 30 days.")}
              disabled={busy}
              className="rounded-lg bg-slate-800 px-3 py-1.5 text-white hover:bg-slate-700 disabled:opacity-50 dark:bg-slate-200 dark:text-slate-900"
            >
              +30 days
            </button>
            <label className="flex items-center gap-1 text-slate-500 dark:text-slate-400">
              Pace
              <select
                value={state?.time_scale ?? 1}
                onChange={(event) =>
                  void run(
                    () => accelerateWorld(Number(event.target.value)),
                    "Time scale updated.",
                  )
                }
                className="rounded-lg border border-slate-300 bg-white px-2 py-1.5 text-xs text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
              >
                {[1, 2, 3, 5, 10].map((scale) => (
                  <option key={scale} value={scale}>
                    ×{scale}
                  </option>
                ))}
              </select>
            </label>
            <div className="flex items-center gap-1 text-slate-500 dark:text-slate-400">
              Seed
              <input
                type="number"
                value={seedInput}
                onChange={(event) => setSeedInput(event.target.value)}
                placeholder="new seed"
                className="w-20 rounded-lg border border-slate-300 bg-white px-2 py-1.5 text-xs text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
              />
              <button
                type="button"
                onClick={() => {
                  const seed = seedInput.trim() ? Number(seedInput) : undefined;
                  setSelectedId(null);
                  void run(
                    () => resetWorld(Number.isNaN(seed) ? undefined : seed),
                    "World reset.",
                  );
                }}
                disabled={busy}
                className="rounded-lg border border-slate-300 px-3 py-1.5 hover:bg-slate-100 disabled:opacity-50 dark:border-slate-700 dark:hover:bg-slate-800"
              >
                Reset
              </button>
            </div>
          </div>
        </div>

        {error && (
          <div className="mt-3 rounded-lg border border-red-300 bg-red-50 px-4 py-2 text-sm text-red-800 dark:border-red-800 dark:bg-red-950 dark:text-red-200">
            {error}
          </div>
        )}

        <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
          <Stat label="Day" value={String(state?.day_number ?? 0)} />
          <Stat
            label="Population"
            value={(stats?.population ?? 0).toLocaleString()}
          />
          <Stat label="Active" value={String(stats?.active ?? 0)} />
          <Stat label="Settlements" value={String(stats?.settlements ?? 0)} />
          <Stat label="Roads" value={String(stats?.roads ?? 0)} />
          <Stat label="Events" value={String(stats?.events ?? 0)} />
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
        <WorldGridMap
          settlements={state?.settlements ?? []}
          roads={state?.roads ?? []}
          seed={state?.seed ?? 0}
          selectedId={selected?.id ?? null}
          onSelect={setSelectedId}
        />

        <div className="flex flex-col gap-4">
          {selected ? (
            <SettlementDetail
              settlement={selected}
              disasterType={disasterType}
              setDisasterType={setDisasterType}
              onDisaster={() => handleDisaster(selected.id)}
              busy={busy}
            />
          ) : (
            <div className="rounded-xl border border-dashed border-slate-300 p-4 text-center text-sm text-slate-400 dark:border-slate-700 dark:text-slate-500">
              Click a settlement on the map to inspect or punish it.
            </div>
          )}

          <div className="rounded-xl border border-slate-200 bg-white p-3 dark:border-slate-800 dark:bg-slate-900">
            <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
              Settlements ({active.length})
            </h3>
            <ul className="flex max-h-56 flex-col gap-1 overflow-y-auto">
              {state?.settlements.map((s) => (
                <li key={s.id}>
                  <button
                    type="button"
                    onClick={() => setSelectedId(s.id)}
                    className={`w-full rounded-lg px-3 py-1.5 text-left text-sm ${
                      s.id === selected?.id
                        ? "bg-indigo-50 text-indigo-700 dark:bg-indigo-500/15 dark:text-indigo-300"
                        : "text-slate-600 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-800"
                    }`}
                  >
                    <span className="flex items-center justify-between gap-2">
                      <span className="truncate">
                        {s.status === "active" ? "●" : "○"} {s.name}
                      </span>
                      <span className="font-mono text-[10px] text-slate-400">
                        lv{s.level} · {s.population.toLocaleString()}
                      </span>
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>

      <div className="rounded-xl border border-slate-200 bg-white p-3 dark:border-slate-800 dark:bg-slate-900">
        <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
          Recent events
        </h3>
        <ul className="flex max-h-72 flex-col gap-1 overflow-y-auto">
          {state?.recent_events.map((event) => (
            <li
              key={event.id}
              className="rounded-lg px-3 py-1.5 text-sm text-slate-600 dark:text-slate-300"
            >
              <span className="mr-2 font-mono text-[10px] text-slate-400">
                D{event.day}
              </span>
              <span
                className={`mr-2 rounded px-1.5 py-0.5 font-mono text-[10px] ${
                  event.severity >= 6
                    ? "bg-red-100 text-red-700 dark:bg-red-900/50 dark:text-red-300"
                    : "bg-slate-100 text-slate-500 dark:bg-slate-800 dark:text-slate-400"
                }`}
              >
                {event.event_type}
              </span>
              {event.title}
            </li>
          ))}
          {state && state.recent_events.length === 0 && (
            <li className="px-3 py-1.5 text-sm text-slate-400 dark:text-slate-500">
              The world is quiet…
            </li>
          )}
        </ul>
      </div>
    </section>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 dark:border-slate-800 dark:bg-slate-950">
      <div className="text-xs text-slate-400 dark:text-slate-500">{label}</div>
      <div className="text-xl font-semibold text-slate-900 dark:text-slate-100">
        {value}
      </div>
    </div>
  );
}

function SettlementDetail({
  settlement,
  disasterType,
  setDisasterType,
  onDisaster,
  busy,
}: {
  settlement: WorldSettlement;
  disasterType: string;
  setDisasterType: (type: string) => void;
  onDisaster: () => void;
  busy: boolean;
}) {
  const rows: [string, string][] = [
    ["Population", settlement.population.toLocaleString()],
    ["Food", settlement.food.toLocaleString()],
    ["Level", String(settlement.level)],
    ["Skill", `Lv ${settlement.skill_level} (${settlement.experience} xp)`],
    ["Terrain", settlement.terrain],
    ["Founded", `Day ${settlement.founded_day}`],
    ["Farmers / Builders", `${settlement.farmers} / ${settlement.builders}`],
    [
      "Merchants / Explorers",
      `${settlement.merchants} / ${settlement.explorers}`,
    ],
  ];
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-3 dark:border-slate-800 dark:bg-slate-900">
      <div className="mb-2 flex items-center justify-between gap-2">
        <h3 className="truncate text-sm font-semibold text-slate-900 dark:text-slate-100">
          {settlement.name}
          {settlement.status === "abandoned" && (
            <span className="ml-2 rounded bg-slate-100 px-1.5 py-0.5 text-[10px] font-medium text-slate-500 dark:bg-slate-800 dark:text-slate-400">
              abandoned
            </span>
          )}
        </h3>
        <span className="font-mono text-[10px] text-slate-400">
          {settlement.id}
        </span>
      </div>
      <dl className="grid grid-cols-2 gap-x-3 gap-y-1 text-xs">
        {rows.map(([label, value]) => (
          <div key={label} className="flex justify-between gap-2">
            <dt className="text-slate-400 dark:text-slate-500">{label}</dt>
            <dd className="font-medium text-slate-700 dark:text-slate-200">
              {value}
            </dd>
          </div>
        ))}
      </dl>
      {settlement.status === "active" && (
        <div className="mt-3 flex items-center gap-2">
          <select
            value={disasterType}
            onChange={(event) => setDisasterType(event.target.value)}
            className="flex-1 rounded-lg border border-slate-300 bg-white px-2 py-1.5 text-xs text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
          >
            {DISASTERS.map((type) => (
              <option key={type} value={type}>
                {type}
              </option>
            ))}
          </select>
          <button
            type="button"
            onClick={onDisaster}
            disabled={busy}
            className="rounded-lg bg-red-700 px-3 py-1.5 text-xs font-medium text-white hover:bg-red-600 disabled:opacity-50"
          >
            Disaster
          </button>
        </div>
      )}
    </div>
  );
}
