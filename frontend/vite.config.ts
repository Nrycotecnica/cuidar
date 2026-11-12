import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { "/api": "http://localhost:8000" },
  },
  // O pedaço da vista 3D (three.js, ~590 kB) passa do aviso padrão de 500 kB, mas
  // é carregado só ao abrir a aba 3D e roda localmente — não vale quebrá-lo.
  build: { outDir: "dist", sourcemap: false, chunkSizeWarningLimit: 700 },
  test: { environment: "node" },
} as any);
