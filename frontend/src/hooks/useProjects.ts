import { useProjects } from "../contexts/ProjectContext";

/** Convenience hook exposing projects with loading/error state. */
export function useProjectList() {
  const { projects, loading, error, refresh } = useProjects();
  return { projects, loading, error, refresh };
}
