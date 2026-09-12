# AI 工作区（`src/components/ai`）

聊天区展示对齐 Codex TUI：`›` 用户输入、`•` 助手输出、`└` 活动详情。

```text
layout.tsx           # 左聊天 / 右结果|设置
scheduler.tsx        # 注册块 + SSE + 编排
Products.tsx         # 右侧普通商品列表 / 比价结果分流
ComparisonResults.tsx # 1688 来源、价格对比图、候选依据
Collapse.tsx         # Foldable：lifecycleOpen + 用户手点锁定
ThinkingOrb.tsx      # Codex 风格活动符 `•`
../lib/agent-run-phase.ts # 前端运行阶段 + UI 映射
useRevealText.ts     # 80ms 合并 + ~2s CharReveal；历史挂载即落定
blocks/              # user / thinking / step / text
```

| 场景 | 行为 |
|------|------|
| 活回合 | SSE delta → 合并 → CharReveal 化开；思考自动摊开，跑完收起 |
| 历史 | 挂载即全文，不重播化开 |
| 等待 | Composer 上方 `• Working (0s • esc to interrupt)`，详情用 `└` |

运行阶段由 `agent-run-phase.ts` 统一映射：

| phase | 展示 |
|------|------|
| `starting` | 正在启动 |
| `thinking` | 思考块流式展开 |
| `executing` | 工具步骤执行中 |
| `outputting` | 正文流式输出 |
| `live` | 浏览器页面直播 |
| `products` | 商品结果展示 |
| `completed` / `failed` | 完成或失败收尾 |
