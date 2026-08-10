import type { PortfolioScore } from "../api/portfolio";

const STATUS_COLOR: Record<string, string> = {
  passing:
    "bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300",
  failing: "bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300",
  pending: "bg-slate-100 text-slate-500 dark:bg-slate-800 dark:text-slate-400",
  clean: "bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300",
  findings:
    "bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300",
};

function scoreColor(score: number): string {
  if (score >= 80) return "text-green-600 dark:text-green-400";
  if (score >= 50) return "text-amber-600 dark:text-amber-400";
  return "text-red-600 dark:text-red-400";
}

export default function HealthCard({
  name,
  score,
}: {
  name: string;
  score: PortfolioScore;
}) {
  const chips: [string, string][] = [
    ["Build", score.build_status],
    ["Tests", score.test_status],
    ["Security", score.security_status],
    [
      "Docs",
      score.documentation_pct > 0 ? `${score.documentation_pct}%` : "none",
    ],
    ["Screenshots", score.screenshots_available ? "yes" : "no"],
  ];

  const reasons: string[] = [];
  if (score.build_status === "pending")
    reasons.push("Build never run (0/30 pts)");
  if (score.build_status === "failing")
    reasons.push("Build failing (0/30 pts)");
  if (score.test_status === "pending")
    reasons.push("Tests never run (0/30 pts)");
  if (score.test_status === "failing") reasons.push("Tests failing (0/30 pts)");
  if (score.security_status === "pending")
    reasons.push("Security scan never run (0/25 pts)");
  if (score.security_status === "findings")
    reasons.push("Open findings (0/25 pts)");
  if (score.documentation_pct === 0) reasons.push("No documentation detected");
  else if (score.documentation_pct < 50)
    reasons.push(`Docs cover ${score.documentation_pct}% of files`);
  if (!score.screenshots_available) reasons.push("No screenshots recorded");

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <h3 className="truncate text-sm font-semibold text-slate-900 dark:text-slate-100">
            {name}
          </h3>
          <p className="truncate font-mono text-[10px] text-slate-400 dark:text-slate-500">
            {score.project_id}
          </p>
        </div>
        <span
          className={`text-3xl font-bold ${scoreColor(score.portfolio_score)}`}
        >
          {score.portfolio_score}
        </span>
      </div>

      <ul className="mt-3 flex flex-wrap gap-1.5">
        {chips.map(([label, value]) => {
          const cls =
            label === "Docs" && value === "none"
              ? STATUS_COLOR.pending
              : label === "Screenshots" && value === "no"
                ? STATUS_COLOR.pending
                : (STATUS_COLOR[value] ?? STATUS_COLOR.pending);
          return (
            <li
              key={label}
              className={`rounded-lg px-2 py-1 text-[10px] font-medium ${cls}`}
            >
              {label}: {value}
            </li>
          );
        })}
      </ul>

      {reasons.length > 0 && (
        <ul className="mt-3 space-y-1 border-t border-slate-100 pt-2 dark:border-slate-800">
          {reasons.map((reason) => (
            <li
              key={reason}
              className="text-[11px] text-slate-500 dark:text-slate-400"
            >
              · {reason}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
