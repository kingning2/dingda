---
name: frontend-architecture
description: 约束叮答前端 pnpm 工作区结构与桌面能力注入。开发 React UI、新增/移动包、判断能力显隐、账号/爬虫 Web 联调时使用。浏览器不支持外部 Agent；客户端才注入。
---

# 前端架构开发规范

先读 [layers.md](../layers.md) 与 [`packages/README.md`](../../packages/README.md)。

## 结论

前端是 **pnpm 工作区**：应用装配在 `apps/web`，可复用能力按业务域拆进 `packages/client/ui-*`。
没有 `src/` 了 —— 不要再往仓库根写前端代码。

参考 sibling `deepseek-harness` 的是 **宿主能力注入**（和它的 `packages/<域>/<包>` 分层思路），
不是把它的 Cordis 插件树搬过来。

## 结构

```text
apps/web/            应用装配 + 启动编排（Vite 根：index.html / 路由表 / 页面 / boot/）
packages/
  contracts/         与 Python 的线协议类型（纯类型）
  client/
    routes/          路由契约（路径常量与解析）
    app-state/       跨域共享 UI 状态（只依赖 contracts 的叶子包）
    runtime/         宿主能力（boot facts）+ HTTP 传输 + Server 状态
    ui-theme/        设计令牌与全局样式
    ui-primitives/   无业务的原子组件 + cn()
    ui-layout/       窗口骨架：外壳 / 标题栏 / 导航栏
    ui-feedback/     错误边界与告警宿主
    ui-ai/            AI 消息渲染
    ui-composer/     输入区
    ui-account/      账号域
    ui-agent/        Agent 域（含运行时发现）
    ui-crawler/      采集域
    ui-home/         首页域
packages-rs/client/  壳：注入能力 + 起停 Server + CLI Runtime
```

**包名 = 一个业务域（`ui-agent`）或一层机制（`runtime`）。**
禁止 `packages/ui`、`packages/shared`、`packages/utils` 这类大杂烩包。

## 依赖方向（硬约束）

```text
apps/web → ui-* → ui-layout/ui-feedback → ui-primitives → ui-theme
叶子：app-state · runtime · routes · contracts
```

1. **叶子包不许引业务包。** 启动编排要组合多个域时放 `apps/web/src/boot/`。
2. **不留「兼容旧 import」的转发壳** —— 转发文件会把环藏起来。直接改调用方。
3. **跨域状态放 `app-state`**，不要寄居在业务包下。

## 能力表

| Capability | Web | Desktop |
|------------|-----|---------|
| 产品 HTTP（账号/爬虫/…） | ✅ | ✅ |
| `externalAgents` | ❌ | ✅ |
| `windowChrome` / 文件对话框 | ❌ | ✅ |

用 `supportsExternalAgents()` / `getHostCapabilities()`（`@v2/runtime/capabilities`），
禁止业务组件继续堆 `isTauri()`。

路由只存在于 `apps/web` 与 `ui-layout`。业务包需要跳转时不要引 `react-router-dom`，
走注入式回调（如 `@v2/runtime/app-alert` 的 `setAppAlertNavigator`）。

## 反例

```text
❌ 新建 packages/ui + packages/shared 当「大杂烩」
❌ 业务包 import react-router-dom 自己跳转
❌ runtime / app-state 引 @v2/ui-*（叶子包反向依赖业务包）
❌ 浏览器 mock 已安装 Codex/Claude
❌ 账号页强制 isTauri() 才打 HTTP
❌ 为外部 Agent 再开一套产品 IPC
```

```text
✅ 浏览器 pnpm dev 直接联调 Server
✅ 客户端注入 externalAgents 后才扫描 CLI
✅ 资产页 Web 只显示账号
✅ 需要跨域编排 → apps/web/src/boot/
```
