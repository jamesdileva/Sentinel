import { useEffect, useState } from "react";

import ServerStatus from "../components/ServerStatus";
import { getSettings } from "../api/settings";
import type {
  SettingGroup,
  SettingsReport,
  SettingsWarning,
} from "../api/settings";

/**
 * Settings page (v1.17.18.0): read-only configuration report — every
 * SENTINEL_* setting with its value, default and source, plus deterministic
 * validation warnings. Purely a status read (docs/01 Rule 2): editing config
 * means editing `.env` and restarting, by design. The home-server panel
 * (ServerStatus) renders below so the machine's live state stays one glance
 * away.
 */
export default function Settings() {
  const [report, setReport] = useState<SettingsReport | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getSettings()
      .then(setReport)
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : String(err));
      });
  }, []);

  return (
    <section aria-label="Settings" className="flex flex-col gap-4">
      <div className="rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
        <h2 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
          Settings
        </h2>
        <p className="text-xs text-slate-400 dark:text-slate-500">
          Read-only configuration report (v1.17.18.0). Edit `.env` and restart
          to change anything — this page never writes server state.
        </p>
      </div>

      {error ? (
        <div
          role="alert"
          className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700 dark:border-red-900 dark:bg-red-950 dark:text-red-300"
        >
          {error}
        </div>
      ) : report === null ? (
        <p className="text-sm text-slate-400">Loading settings…</p>
      ) : (
        <>
          <WarningsBanner warnings={report.warnings} />
          {report.groups.map((group) => (
            <SettingsTable key={group.name} group={group} />
          ))}
        </>
      )}

      <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
        Home server
      </h3>
      <ServerStatus />
    </section>
  );
}

function WarningsBanner({ warnings }: { warnings: SettingsWarning[] }) {
  if (warnings.length === 0) {
    return (
      <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-700 dark:border-emerald-900 dark:bg-emerald-950 dark:text-emerald-300">
        No configuration warnings — everything checks out.
      </div>
    );
  }
  return (
    <div
      role="alert"
      className="rounded-xl border border-amber-200 bg-amber-50 p-4 dark:border-amber-900 dark:bg-amber-950"
    >
      <h3 className="text-sm font-semibold text-amber-900 dark:text-amber-200">
        Configuration warnings ({warnings.length})
      </h3>
      <ul className="mt-2 space-y-1">
        {warnings.map((warning) => (
          <li key={warning.key} className="text-sm text-amber-800 dark:text-amber-300">
            <span
              className={`mr-1 inline-block rounded px-1 text-xs font-semibold uppercase ${
                warning.level === "error"
                  ? "bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300"
                  : "bg-amber-100 text-amber-700 dark:bg-amber-900 dark:text-amber-300"
              }`}
            >
              {warning.level}
            </span>
            {warning.message}
          </li>
        ))}
      </ul>
    </div>
  );
}

function SettingsTable({ group }: { group: SettingGroup }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900">
      <h3 className="border-b border-slate-200 px-4 py-2 text-sm font-semibold text-slate-900 dark:border-slate-800 dark:text-slate-100">
        {group.name}
      </h3>
      <table className="w-full text-sm">
        <tbody>
          {group.items.map((item) => (
            <tr
              key={item.key}
              className="border-b border-slate-100 last:border-0 dark:border-slate-800"
            >
              <th
                scope="row"
                className="px-4 py-2 text-left font-normal text-slate-500 dark:text-slate-400"
              >
                {item.label}
                <span className="ml-2 font-mono text-xs text-slate-300 dark:text-slate-600">
                  {item.key}
                </span>
              </th>
              <td className="px-4 py-2">
                <code className="break-all font-mono text-xs text-slate-900 dark:text-slate-100">
                  {item.value}
                </code>
              </td>
              <td className="px-4 py-2 text-xs text-slate-400 dark:text-slate-500">
                default: {item.default}
              </td>
              <td className="px-4 py-2 text-right">
                <span
                  className={`rounded px-1.5 py-0.5 text-xs font-semibold ${
                    item.source === "env"
                      ? "bg-sky-100 text-sky-700 dark:bg-sky-900 dark:text-sky-300"
                      : "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300"
                  }`}
                >
                  {item.source}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}