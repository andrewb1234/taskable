import path from "node:path";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    port: 5173,
    // Proxy REST + SSE to the local FastAPI process so the UI can use
    // relative URLs and avoid CORS friction during development.
    proxy: {
      "/api/v1": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});
