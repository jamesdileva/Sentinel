import { BrowserRouter } from "react-router";

import { BuildProvider } from "./contexts/BuildContext";
import { ProjectProvider } from "./contexts/ProjectContext";
import { UIProvider } from "./contexts/UIContext";
import { AppRoutes } from "./routes";

export default function App() {
  return (
    <BrowserRouter>
      <UIProvider>
        <ProjectProvider>
          <BuildProvider>
            <AppRoutes />
          </BuildProvider>
        </ProjectProvider>
      </UIProvider>
    </BrowserRouter>
  );
}
