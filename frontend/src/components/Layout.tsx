import { NavLink, Outlet } from "react-router";

import { useUI } from "../contexts/UIContext";
import { NAV_ITEMS } from "./nav";

export default function Layout() {
  const { dark, toggleDark, sidebarOpen, setSidebarOpen } = useUI();

  const sidebar = (
    <nav className="flex h-full flex-col gap-1 p-4">
      <div className="mb-4 flex items-center gap-2 px-2">
        <span className="text-xl text-indigo-500 dark:text-indigo-400">◉</span>
        <span className="text-lg font-semibold tracking-tight text-slate-900 dark:text-slate-100">
          Sentinel
        </span>
      </div>
      {NAV_ITEMS.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          end={item.to === "/"}
          onClick={() => setSidebarOpen(false)}
          className={({ isActive }) =>
            `flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
              isActive
                ? "bg-indigo-50 text-indigo-700 dark:bg-indigo-500/15 dark:text-indigo-300"
                : "text-slate-600 hover:bg-slate-100 hover:text-slate-900 dark:text-slate-400 dark:hover:bg-slate-800 dark:hover:text-slate-200"
            }`
          }
        >
          <span aria-hidden="true">{item.icon}</span>
          {item.label}
        </NavLink>
      ))}
    </nav>
  );

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 dark:bg-slate-950 dark:text-slate-100">
      <aside className="fixed inset-y-0 left-0 z-40 hidden w-60 border-r border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900 lg:block">
        {sidebar}
      </aside>

      {sidebarOpen && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div
            className="absolute inset-0 bg-slate-900/50"
            onClick={() => setSidebarOpen(false)}
          />
          <aside className="absolute inset-y-0 left-0 w-60 border-r border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900">
            {sidebar}
          </aside>
        </div>
      )}

      <div className="lg:pl-60">
        <header className="sticky top-0 z-30 flex h-14 items-center gap-4 border-b border-slate-200 bg-white/80 px-4 backdrop-blur dark:border-slate-800 dark:bg-slate-900/80">
          <button
            type="button"
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="rounded-lg p-2 text-slate-600 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-800 lg:hidden"
            aria-label="Toggle navigation"
          >
            ☰
          </button>
          <h1 className="flex-1 text-sm font-semibold uppercase tracking-widest text-slate-500 dark:text-slate-400">
            Dashboard
          </h1>
          <button
            type="button"
            onClick={toggleDark}
            className="rounded-lg p-2 text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800"
            aria-label="Toggle dark mode"
          >
            {dark ? "☀" : "☾"}
          </button>
        </header>

        <main className="p-4 sm:p-6 lg:p-8">
          <Outlet />
        </main>
      </div>

      <Toasts />
    </div>
  );
}

function Toasts() {
  const { toasts, dismissToast } = useUI();
  if (toasts.length === 0) return null;
  return (
    <div className="pointer-events-none fixed bottom-4 right-4 z-50 flex flex-col gap-2">
      {toasts.map((toast) => (
        <button
          key={toast.id}
          type="button"
          onClick={() => dismissToast(toast.id)}
          className={`pointer-events-auto rounded-lg border px-4 py-2 text-sm shadow-lg backdrop-blur ${
            toast.kind === "error"
              ? "border-red-300 bg-red-50 text-red-800 dark:border-red-800 dark:bg-red-950 dark:text-red-200"
              : toast.kind === "success"
                ? "border-emerald-300 bg-emerald-50 text-emerald-800 dark:border-emerald-800 dark:bg-emerald-950 dark:text-emerald-200"
                : "border-slate-300 bg-white text-slate-800 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200"
          }`}
        >
          {toast.message}
        </button>
      ))}
    </div>
  );
}
