import { Navigate, Route, Routes } from "react-router";

import Layout from "../components/Layout";
import Builds from "../pages/Builds";
import Dashboard from "../pages/Dashboard";
import KnowledgeExplorer from "../pages/KnowledgeExplorer";
import Observatory from "../pages/Observatory";
import Portfolio from "../pages/Portfolio";
import Projects from "../pages/Projects";
import Security from "../pages/Security";
import Sessions from "../pages/Sessions";
import Settings from "../pages/Settings";

export function AppRoutes() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Dashboard />} />
        <Route path="projects" element={<Projects />} />
        <Route path="builds" element={<Builds />} />
        <Route path="sessions" element={<Sessions />} />
        <Route path="security" element={<Security />} />
        <Route path="knowledge" element={<KnowledgeExplorer />} />
        <Route path="portfolio" element={<Portfolio />} />
        <Route path="observatory" element={<Observatory />} />
        <Route path="system" element={<Settings />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
