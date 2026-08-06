import { useEffect, useState } from "react";

import {
  getBestCandidates,
  getFeatureMatrix,
  getScores,
  type FeatureMatrix as FeatureMatrixData,
  type PortfolioCandidate,
  type PortfolioScore,
} from "../api/portfolio";
import { listProjects } from "../api/projects";
import FeatureMatrix from "../components/FeatureMatrix";
import HealthCard from "../components/HealthCard";

export default function Portfolio() {
  const [scores, setScores] = useState<PortfolioScore[]>([]);
  const [candidates, setCandidates] = useState<PortfolioCandidate[]>([]);
  const [matrix, setMatrix] = useState<FeatureMatrixData | null>(null);
  const [names, setNames] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const [projectList, scoreRows, candidateRows, featureMatrix] =
          await Promise.all([
            listProjects(),
            getScores(),
            getBestCandidates(70),
            getFeatureMatrix(),
          ]);
        if (cancelled) return;
        setScores(scoreRows);
        setCandidates(candidateRows);
        setMatrix(featureMatrix);
        setNames(
          Object.fromEntries(
            projectList.projects.map((p) => [p.id, p.name]),
          ),
        );
        setError(null);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Cannot load portfolio.");
        }
      }
    };
    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <section
      aria-label="Portfolio intelligence"
      className="flex flex-col gap-4"
    >
      <div className="rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
        <h2 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
          Portfolio Intelligence
        </h2>
        <p className="text-xs text-slate-400 dark:text-slate-500">
          Deterministic health: build 30 · tests 30 · security 25 · docs 15 —
          components you have not run yet score 0.
        </p>
        {error && (
          <div className="mt-3 rounded-lg border border-red-300 bg-red-50 px-4 py-2 text-sm text-red-800 dark:border-red-800 dark:bg-red-950 dark:text-red-200">
            {error}
          </div>
        )}
      </div>

      <div>
        <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
          Health scores ({scores.length})
        </h3>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {scores.map((score) => (
            <HealthCard
              key={score.project_id}
              name={names[score.project_id] ?? score.project_id}
              score={score}
            />
          ))}
          {scores.length === 0 && !error && (
            <div className="rounded-xl border border-dashed border-slate-300 p-4 text-center text-sm text-slate-400 dark:border-slate-700 dark:text-slate-500">
              No projects indexed. Add one via the CLI indexer.
            </div>
          )}
        </div>
      </div>

      <div>
        <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
          Best candidates (score ≥ 70)
        </h3>
        {candidates.length === 0 ? (
          <div className="rounded-xl border border-dashed border-slate-300 p-4 text-center text-sm text-slate-400 dark:border-slate-700 dark:text-slate-500">
            Nothing at or above 70 yet.
          </div>
        ) : (
          <ul className="flex flex-col gap-2">
            {candidates.map((candidate) => (
              <li
                key={candidate.project_id}
                className="flex items-center justify-between gap-3 rounded-xl border border-slate-200 bg-white px-4 py-3 dark:border-slate-800 dark:bg-slate-900"
              >
                <div className="min-w-0">
                  <div className="truncate text-sm font-semibold text-slate-900 dark:text-slate-100">
                    {candidate.project_name}
                  </div>
                  {candidate.missing.length > 0 ? (
                    <div className="text-xs text-slate-400 dark:text-slate-500">
                      Missing: {candidate.missing.join(", ")}
                    </div>
                  ) : (
                    <div className="text-xs text-green-600 dark:text-green-400">
                      Nothing missing
                    </div>
                  )}
                </div>
                <span className="text-xl font-bold text-slate-900 dark:text-slate-100">
                  {candidate.score}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div>
        <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
          Feature matrix
        </h3>
        {matrix ? (
          <FeatureMatrix matrix={matrix} />
        ) : (
          !error && (
            <div className="rounded-xl border border-dashed border-slate-300 p-4 text-center text-sm text-slate-400 dark:border-slate-700 dark:text-slate-500">
              Loading…
            </div>
          )
        )}
      </div>
    </section>
  );
}