---
name: frontend-architecture
description: 约束叮答前端 web-first 与桌面能力注入。开发 React UI、拆分目录、判断是否需要 packages、外部 CLI Agent 显隐、账号/爬虫 Web 联调时使用。浏览器不支持外部 Agent；客户端才注入。
---

# 前端架构开发规范

先读 [layers.md](../layers.md)。

## 结论

**不要引入 `packages/` / `apps/` monorepo。** 一个 Vite `src/` 足够。

参考 sibling `deepseek-harness` 的是「宿主注入能力」，不是把它的 Cordis 插件树搬过来。

## 拆分方式

```text
src/                 产品 UI（主开发）
  components/        功能界面（尽量不 import @tauri-apps）
  contracts/         DTO
  lib/
    capabilities.ts  宿主能力（boot facts）
    server.ts        Server 连接（Web 默认本机；桌面由壳注入）
    window.ts        窗口铬（桌面）
    agent-runtime*   外部 CLI Agent（桌面）
  providers/         React context
src-tauri/           壳：注入能力 + 起停 Server + CLI Runtime
```

## 能力表

| Capability | Web | Desktop |
|------------|-----|---------|
| 产品 HTTP（账号/爬虫/…） | ✅ | ✅ |
| `externalAgents` | ❌ | ✅ |
| `windowChrome` / 文件对话框 | ❌ | ✅ |

用 `supportsExternalAgents()` / `getHostCapabilities()`，禁止业务组件继续堆 `isTauri()`。

## 反例

```text
❌ packages/ui + packages/shared「以后给桌面用」
❌ 浏览器 mock 已安装 Codex/Claude
❌ 账号页强制 isTauri() 才打 HTTP
❌ 为外部 Agent 再开一套产品 IPC
```

```text
✅ 浏览器 pnpm dev 直接联调 Server
✅ 客户端注入 externalAgents 后才扫描 CLI
✅ 资产页 Web 只显示账号
```
