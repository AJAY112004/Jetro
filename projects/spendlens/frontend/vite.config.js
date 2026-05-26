import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    host: "127.0.0.1",
    port: 5173,
    proxy: {
      // Proxies /api/* (including /api/download-pdf) → Flask :5050 (same-origin in dev).
      "/api": {
        target: "http://127.0.0.1:5050",
        changeOrigin: true,
        secure: false,
        cookieDomainRewrite: "127.0.0.1",
      },
    },
  },
});
