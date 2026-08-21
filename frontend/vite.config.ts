import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8420",
        changeOrigin: true,
        // v1.17.18.4 (audit2 F2): without ws:true the dev proxy never
        // forwards the /api/v1/ws/jobs upgrade, so development never
        // exercised the live path (prod is same-origin and unaffected).
        ws: true,
      },
    },
  },
});
