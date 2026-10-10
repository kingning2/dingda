# pi 扩展（移植自 addyosmani/agent-skills hooks，MIT）

上游的 Claude Code shell hooks 已移植为 pi 原生 TypeScript 扩展。放在 `.pi/extensions/`
即被 pi 自动发现加载（项目受信任后生效），`/reload` 可热载。上游 LICENSE 见
[`.agents/references/LICENSE-agent-skills`](../.agents/references/LICENSE-agent-skills)。

| 上游 hook（Claude Code） | pi 扩展 | 事件映射 |
|---|---|---|
| `sdd-cache-pre.sh` / `sdd-cache-post.sh`（PreToolUse/PostToolUse: WebFetch） | `sdd-cache.ts` | `tool_call`（任意带 url 的工具）→ 304 复验命中则 `{block, reason:缓存正文}`；`tool_result` → 抓 ETag/Last-Modified 落盘 |
| `simplify-ignore.sh`（PreToolUse: Read；PostToolUse: Edit\|Write；Stop） | `simplify-ignore.ts` | `tool_call:read` → 备份+过滤；`tool_result:edit/write` → 展开+重过滤；`agent_settled`+`session_shutdown` → 兜底展开（等价 Stop） |
| `session-start.sh`（注入 meta-skill） | **未移植，有意跳过** | pi 原生按 description 路由技能；上游 hook 头部注释自己写明：有原生路由的宿主不要挂，避免双路由 |

## sdd-cache（source-driven-development 的文档缓存）

- 键 = `sha256(url)` 前 32 hex；正文存 `.pi/sdd-cache/<key>.json`。
- **无 TTL**：命中必须经源站 `304 Not Modified` 确认；无 ETag/Last-Modified 的站点永不缓存。
- 匹配任意 `input.url` 为 http(s) 的工具调用（覆盖本会话的 `fetch_content` 及将来的内置 fetch）。
- 调试：`SDD_CACHE_DEBUG=1` 启动 pi，或 `touch .pi/sdd-cache/.debug`；日志在同目录 `.debug.log`。
- 手动失效：删除对应 `.pi/sdd-cache/<key>.json`。

## simplify-ignore（/code-simplify 的块级保护）

在代码里标注后，模型在 `/code-simplify` 期间看不到保护块，回合结束自动还原：

```js
/* simplify-ignore-start: perf-critical */
result[0] = buf[0] ^ key[0];   // 任何注释风格都行：// /* # <!--
/* simplify-ignore-end */
```

- 备份与块存储：`.pi/.simplify-ignore-cache/<fid>.*`（fid = sha1(路径) 前 16 hex）。
- 展开三级匹配：精确占位符 → 去 reason → 裸 `BLOCK_<hash>`；模型改写占位符会留下
  装饰性残渣并告警（与上游一致的已文档化行为）；整体重写会把重写稿存为 `*.recovered`。
- 崩溃恢复：会话内 `/simplify-restore` 命令，或下次会话任何回合落定时自动兜底。
- 已知限制（继承上游）：单行块隐藏整行；`*/`/`-->` 之外的注释闭合符可能产生不平衡占位符。

## 与上游的差异

- 缓存/备份根从 `.claude/` 移到 `.pi/`（已加入 `.gitignore`）。
- 警告从 stderr 改为 `ctx.ui.notify`（TUI 可见）。
- 新增 `/simplify-restore` 命令（上游靠手动执行脚本恢复）。
- sdd-cache 匹配从固定 `WebFetch` 改为任意带 `url` 的工具（pi 无内置 fetch 工具名可匹配）。

## 验证

```bash
bun .pi/tests/_test.ts   # 37 项：纯函数往返 + mock 事件注册 + 真实磁盘生命周期
```
