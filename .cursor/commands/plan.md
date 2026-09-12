---
description: 变更前最小计划。开发 Agent / Crawler / Browser / Tool 或跨层改动时使用。
---

先输出一个最小计划，不直接改代码。计划必须包含：

1. **边界定位**
   - 改动属于 React 产品 UI、Rust 壳、还是 Python Server
   - 产品 API 走 Python HTTP/SSE，不要经 Rust 转发
   - 壳能力（对话框、Python 生命周期、CLI Agent Runtime）才走现有 `packages-rs/client/src/commands/`
   - 涉及 Agent / Crawler / Browser / Tool 时，先读 `.agents/skills/layers.md` 与对应 SKILL

2. **契约检查**
   - 产品 HTTP：`server/src/contracts/` 与 `packages/contracts/src/` 对齐；顺序 Contract → Python → React（不必改 Rust）
   - CLI Agent 事件：Python SSE 与 `packages/contracts/src/agent-event.ts`；启动在 `server/src/agent/runtimes/`，探测在 Tauri
   - Tool：`server/src/tools/`（每工具一文件 + registry）

3. **最小改动范围**
   - 只列要改的目录与文件类型
   - 新平台只加 `server/src/crawler/sources/<id>/`
   - 新浏览器只加 `server/src/browser/adapters/`
   - 说明不改哪些无关区域

4. **验证计划**
   - 前端：`pnpm` 相关脚本（如有）
   - Python：在 `server/` 下 pytest，按改动范围跑 `tests/`
   - 不要调用已不存在的 `skills/opendesk/scripts/*.py`
