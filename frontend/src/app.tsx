import { BrowserRouter } from "react-router";

import ErrorBoundary from "./components/ErrorBoundary";
import { ProjectProvider } from "./contexts/ProjectContext";
import { UIProvider } from "./contexts/UIContext";
import { AppRoutes } from "./routes";

export default function App() {
  return (
    <BrowserRouter>
      <ErrorBoundary>
        <UIProvider>
          <ProjectProvider>
            <AppRoutes />
          </ProjectProvider>
        </UIProvider>
      </ErrorBoundary>
    </BrowserRouter>
  );
}
