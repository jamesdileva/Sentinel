import type { FeatureMatrix as FeatureMatrixData } from "../api/portfolio";

function symbolColor(symbol: string): string {
  if (symbol === "✓") return "text-green-600 dark:text-green-400";
  if (symbol === "⚠") return "text-amber-500 dark:text-amber-400";
  return "text-slate-300 dark:text-slate-600";
}

export default function FeatureMatrix({
  matrix,
}: {
  matrix: FeatureMatrixData;
}) {
  return (
    <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-slate-200 text-left dark:border-slate-800">
            <th className="px-3 py-2 text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
              Project
            </th>
            {matrix.features.map((feature) => (
              <th
                key={feature}
                className="px-3 py-2 text-center text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400"
              >
                {feature}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {matrix.projects.map((name, rowIndex) => (
            <tr
              key={name}
              className="border-b border-slate-100 last:border-0 dark:border-slate-800"
            >
              <td className="px-3 py-2 font-medium text-slate-800 dark:text-slate-100">
                {name}
              </td>
              {(matrix.matrix[rowIndex] ?? []).map((symbol, colIndex) => (
                <td
                  key={matrix.features[colIndex]}
                  className={`px-3 py-2 text-center text-lg font-bold ${symbolColor(symbol)}`}
                >
                  {symbol}
                </td>
              ))}
            </tr>
          ))}
          {matrix.projects.length === 0 && (
            <tr>
              <td
                colSpan={matrix.features.length + 1}
                className="px-3 py-4 text-center text-sm text-slate-400 dark:text-slate-500"
              >
                No projects indexed yet.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}