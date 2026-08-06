import { Navigate, Route, Routes } from "react-router";

import Layout from "../components/Layout";
import Dashboard from "../pages/Dashboard";
import KnowledgeExplorer from "../pages/KnowledgeExplorer";
import Observatory from "../pages/Observatory";
import Placeholder from "../pages/Placeholder";
import Portfolio from "../pages/Portfolio";
import WorldSimulatorPage from "../pages/WorldSimulatorPage";

export function AppRoutes() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Dashboard />} />
        <Route path="projects" element={<Placeholder title="Projects" />} />
        <Route path="builds" element={<Placeholder title="Builds" />} />
        <Route path="security" element={<Placeholder title="Security" />} />
        <Route path="knowledge" element={<KnowledgeExplorer />} />
        <Route path="world" element={<WorldSimulatorPage />} />
        <Route path="portfolio" element={<Portfolio />} />
        <Route path="observatory" element={<Observatory />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
