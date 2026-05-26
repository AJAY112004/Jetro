import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react-oxc";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");

  const devHost = env.VITE_DEV_HOST || "127.0.0.1";
  const apiProxyTarget = env.VITE_API_PROXY_TARGET || "http://127.0.0.1:5050";
  const cookieDomainRewrite = (() => {
    try {
      return new URL(apiProxyTarget).hostname;
    } catch {
      return "127.0.0.1";
    }
  })();

  return {
    plugins: [react()],
    server: {
      host: devHost,
      port: 5173,
      proxy: {
        // Proxies /api/* (including /api/download-pdf) → Flask (same-origin in dev).
        "/api": {
          target: apiProxyTarget,
          changeOrigin: true,
          secure: false,
          cookieDomainRewrite: cookieDomainRewrite,
        },
      },
    },
    build: {
      // Production hardening defaults.
      sourcemap: false,
      target: "es2018",
      chunkSizeWarningLimit: 600,
    },
  };
});
