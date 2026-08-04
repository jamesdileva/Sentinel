import { Navigate, Route, Routes } from "react-router";

import Layout from "../components/Layout";
import Dashboard from "../pages/Dashboard";
import Placeholder from "../pages/Placeholder";

export function AppRoutes() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Dashboard />} />
        <Route path="projects" element={<Placeholder title="Projects" />} />
        <Route path="builds" element={<Placeholder title="Builds" />} />
        <Route path="security" element={<Placeholder title="Security" />} />
        <Route path="knowledge" element={<Placeholder title="Knowledge" />} />
        <Route path="portfolio" element={<Placeholder title="Portfolio" />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
