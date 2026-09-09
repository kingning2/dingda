# AI 工作区（`src/components/ai`）

对齐 OpenDesign chat 观感。

```text
layout.tsx           # 左聊天 / 右结果|设置
scheduler.tsx        # 注册块 + SSE + 编排
Collapse.tsx         # Foldable：lifecycleOpen + 用户手点锁定
ThinkingOrb.tsx      # 等待态
useRevealText.ts     # 100ms 合并 + ~2s CharReveal；历史挂载即落定
useThinkingFollow.ts # 思考区内贴底跟随
blocks/              # user / thinking / step / text
```

| 场景 | 行为 |
|------|------|
| 活回合 | SSE delta → 合并 → CharReveal 化开；思考自动摊开，跑完收起 |
| 历史 | 挂载即全文，不重播化开 |
| 等待 | 时间线底 + Composer 上 ThinkingOrb |
