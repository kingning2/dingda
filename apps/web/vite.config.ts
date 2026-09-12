import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from "node:path";

const host = process.env.TAURI_DEV_HOST;

export default defineConfig(async () => ({
  // 本应用是 Vite 根：index.html 与 dist/ 都以本目录为基准。
  // 显式声明而不是依赖 cwd，否则从仓库根直接调 vite 会把 dist 吐到根上。
  root: __dirname,
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      // 只登记应用自身源码。@v2/* 刻意不在这里 —— 那些必须走 pnpm 工作区
      // 软链解析；在这里再加一层别名会把「工作区是否真的接通」掩盖掉。
      "@web": path.resolve(__dirname, "./src"),
    },
  },
  clearScreen: false,
  server: {
    port: 1420,
    strictPort: true,
    host: host || false,
    hmr: host
      ? { protocol: "ws", host, port: 1421 }
      : undefined,
    watch: { ignored: ["**/packages-rs/**"] },
  },
}));
