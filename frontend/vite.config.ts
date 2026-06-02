import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
      "/tiles": {
        // martin (Rust MVT server) sur port 3010 par défaut — cohérent avec
        // docker-compose.yml (MARTIN_PORT_HOST=3010 pour éviter conflit avec
        // d'autres projets Node squattant 3000).
        target: process.env.MARTIN_URL || "http://localhost:3010",
        changeOrigin: true,
        rewrite: (p) => p.replace(/^\/tiles/, ""),
      },
    },
  },
});
