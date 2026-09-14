# AI 工作区（`ui-ai/src`）

聊天区展示对齐 Codex TUI：`›` 用户输入、`•` 助手输出、`└` 活动详情。

## 分层

```text
layout.tsx             # 分栏装配：左 Chat / 右 结果|设置。唯一持有 work 状态与持久化
send.ts                # 发起一次 Agent 运行：乐观插入 → SSE → 逐事件更新 detail
agent-output.ts        # 工具输出 → 商品 / 比价视图的解析与合并

chat/                  # 聊天记录（本目录的核心）
  types.ts             # ChatBlock / ChatTurn / 块组件契约
  registry.ts          # registerBlock / resolveBlock
  schedule.ts          # 纯函数：detail → ChatTurn[]（可脱离 React 单测）
  chat-block.tsx       # 注册表唯一消费点；副作用导入 ../blocks
  chat-turn.tsx        # 一轮：用户块 + 助手块
  working-status.tsx   # Codex 状态行 + `└` 详情推导
  use-sticky-and-follow.ts  # sticky 分区 + 跟随底部
  chat.tsx             # Chat 面板：轮次 + 虚拟滚动 + 装配输入框

blocks/                # 4 个块，各自在文件末尾自注册
  index.ts             # 装配点：副作用导入全部块
  user.tsx  thinking.tsx  step.tsx  text.tsx

composer-footer.tsx    # 输入框（无状态包装）
session.ts             # 历史加载：SQLite → session 快照 → 首页草稿 → 空壳
Products.tsx           # 右侧普通商品列表 / 比价结果分流
ComparisonResults.tsx  # 1688 来源、价格对比图、候选依据
Collapse.tsx           # Foldable：lifecycleOpen + 用户手点锁定
ThinkingOrb.tsx        # Codex 风格活动符 `•`
useRevealText.ts       # 80ms 合并 + ~2s CharReveal；历史挂载即落定
stick-to-bottom.ts     # 是否贴底的纯函数
markdown/              # Markdown 渲染 + 代码块 + 链接
```

## 加一个聊天块

四步，**零处改 `Chat`**：

1. 新建 `blocks/<name>.tsx`，写组件（props 类型用 `ChatBlockProps<"<kind>">`）
2. 文件末尾 `registerBlock("<kind>", <Name>Block)`
3. `chat/types.ts` 的 `ChatBlock` 联合加一支
4. `blocks/index.ts` 加一行 `import "./<name>"`

详见 `chat/README.md`。

## 行为约定

| 场景 | 行为 |
|------|------|
| 活回合 | SSE delta → 合并 → CharReveal 化开；思考块在流式期间不显示正文，反馈由状态行承担 |
| 历史 | 挂载即全文，不重播化开；`busy=false`、`phase=null` |
| 等待 | Composer 上方 `• Working (0s • esc to interrupt)`，详情用 `└` |
| 滚动 | 用户脱离底部后不再自动跟随；滚回底部自动恢复 |
| 取消 | 活回合按 Esc |

运行阶段由 `@v2/ui-agent/agent-run-phase` 统一映射：

| phase | 展示 |
|------|------|
| `starting` | 正在启动 |
| `thinking` | 思考块流式展开 |
| `executing` | 工具步骤执行中 |
| `outputting` | 正文流式输出 |
| `live` | 浏览器页面直播 |
| `products` | 商品结果展示 |
| `completed` / `failed` | 完成或失败收尾 |
