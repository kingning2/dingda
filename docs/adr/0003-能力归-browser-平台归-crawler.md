# ADR-0003：能力归 Browser、平台归 Crawler 的分层铁律

状态：采纳 · 日期：2026-02（规则先于守卫落地，`scripts/check/layers-guard.mjs`）

## 背景

爬取能力是叮答的核心资产，历史上最容易腐烂的地方就是"谁有权碰浏览器"：
Agent 想直接开 Playwright 截图，Tool 想直接查 SQLite，Crawler 想绕过浏览器
接口自己造 CDP 连接 —— 每一个捷径都会让反检测、会话管理和风控恢复失去唯一收口。

## 决策

八条核心规则的机械可查子集固化为守卫（AGENTS.md §2 为全文）：

- **能力归 Browser**：Playwright / Camoufox / CDP 只许出现在
  `browser/adapters/<browser>`；其他包一律经 Browser Interface。
- **平台归 Crawler**：闲鱼 / 1688 / 小红书 的解析与平台特例只进
  `crawler/sources/<platform>`，不进 core、不进 agent。
- **登录语义归 channels**：二维码、Cookie、风控恢复只进 `channels/<platform>`。
- **Agent / Tool 一律经 Tool → Crawler → Browser**：agent 与 tools 包禁直连
  playwright / camoufox / sqlite（layers-guard 规则 A）；api / domains 禁直连
  浏览器（规则 C）；crawler 禁直 import playwright（规则 B）。

禁止为此新增 Rust Crawler/Browser/DB：Rust 壳只做打包与 OS 能力。

## 后果

- 守卫误报率必须保持为零：任何新规则先核绿（当前代码全绿）再入表。
- 特例需求（如某平台需要原生 WS）走对应包的内部模块，不走跨层 import。
- 守卫在观察期（CI `continue-on-error`），两周无误报后转阻断。
