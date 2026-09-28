import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev-time proxy so the React app can call /api and /ws on the same
// origin as the FastAPI backend (avoids CORS/WebSocket-origin issues
// while developing locally). In production, set VITE_API_BASE and
// VITE_WS_BASE env vars instead (see .env.example / README).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": { target: "http://localhost:8000", changeOrigin: true },
      "/ws": { target: "ws://localhost:8000", ws: true },
    },
  },
});
