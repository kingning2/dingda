/**
 * 给 debug 版壳用的静态前端服务。
 *
 * 为什么必须有它：
 *   `cargo build` 产出的 debug 壳里 `cfg!(dev) == true`，于是 Tauri 走 `devUrl`
 *   （`tauri.conf.json` 里的 `http://localhost:1420`），而**不是**嵌入的
 *   `frontendDist`。1420 上没东西时，窗口能起来但页面白屏 —— 更隐蔽的是，
 *   前端 JS 从未执行，于是不会调 `/v1/bootstrap`，Server 的 `phase` 会永远停在
 *   `shell`，看起来像"后端没预热"。
 *
 *   这里顶一个只读静态服务，比拉起重型 Vite dev server 快得多，且用的是
 *   生产产物（`apps/web/dist`），更贴近真实形态。
 *
 * 注意：监听时**不指定 host**，让 Node 同时绑 IPv4/IPv6 —— Windows 上
 * `localhost` 常解析到 `::1`，只绑 `127.0.0.1` 会连不上。
 */
import fs from "node:fs";
import http from "node:http";
import path from "node:path";

const MIME: Record<string, string> = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".mjs": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".svg": "image/svg+xml",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".webp": "image/webp",
  ".ico": "image/x-icon",
  ".woff": "font/woff",
  ".woff2": "font/woff2",
  ".txt": "text/plain; charset=utf-8",
};

export type StaticServer = { close: () => Promise<void>; port: number };

/** 起一个服务 `rootDir` 的静态服务；未命中的路径回落到 index.html（SPA 语义）。 */
export function startStaticServer(rootDir: string, port: number): Promise<StaticServer> {
  const root = path.resolve(rootDir);

  const server = http.createServer((req, res) => {
    const rawPath = decodeURIComponent((req.url ?? "/").split("?")[0]);
    let filePath = path.join(root, rawPath);

    // 目录穿越防护：解析后必须仍在 root 之内。
    if (!path.resolve(filePath).startsWith(root)) {
      res.writeHead(403).end("forbidden");
      return;
    }

    if (!fs.existsSync(filePath) || fs.statSync(filePath).isDirectory()) {
      filePath = path.join(root, "index.html");
    }

    const ext = path.extname(filePath).toLowerCase();
    res.writeHead(200, {
      "Content-Type": MIME[ext] ?? "application/octet-stream",
      "Cache-Control": "no-store",
    });
    fs.createReadStream(filePath).pipe(res);
  });

  return new Promise((resolve, reject) => {
    server.once("error", reject);
    server.listen(port, () => {
      resolve({
        port,
        close: () =>
          new Promise<void>((done) => {
            server.close(() => done());
          }),
      });
    });
  });
}
