import { createContext, useContext, useMemo, useState } from "react";

import type { BuildJob } from "../api/builds";

interface BuildContextValue {
  activeJobs: BuildJob[];
  history: BuildJob[];
  trackJob: (job: BuildJob) => void;
  setJobStatus: (jobId: string, status: BuildJob["status"]) => void;
}

const BuildContext = createContext<BuildContextValue | null>(null);

export function BuildProvider({ children }: { children: React.ReactNode }) {
  const [activeJobs, setActiveJobs] = useState<BuildJob[]>([]);
  const [history, setHistory] = useState<BuildJob[]>([]);

  const value = useMemo<BuildContextValue>(
    () => ({
      activeJobs,
      history,
      trackJob: (job) =>
        setActiveJobs((current) =>
          current.some((j) => j.id === job.id) ? current : [...current, job],
        ),
      setJobStatus: (jobId, status) => {
        setActiveJobs((current) =>
          current.map((j) =>
            j.id === jobId ? { ...j, status } : j,
          ),
        );
        setHistory((current) =>
          current.map((j) => (j.id === jobId ? { ...j, status } : j)),
        );
      },
    }),
    [activeJobs, history],
  );

  return <BuildContext.Provider value={value}>{children}</BuildContext.Provider>;
}

export function useBuilds(): BuildContextValue {
  const ctx = useContext(BuildContext);
  if (!ctx) throw new Error("useBuilds must be used within a BuildProvider");
  return ctx;
}
