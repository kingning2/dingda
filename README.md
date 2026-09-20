<p align="center">
  <img src="./apps/web/public/logo.svg" alt="叮答" width="64" />
</p>

<h1 align="center">叮答 DingDa</h1>

<p align="center">
  用自然语言做选品调研的桌面工作台 —— 搜闲鱼、对 1688、采小红书。
</p>

<p align="center">
  <img src="./apps/web/public/home.png" alt="叮答首页" width="900" />
</p>

---

## Introduction

叮答是一个桌面端选品工作台：React 界面 + Tauri 壳 + Python Server。  
你在对话里描述需求，Agent 调用内置工具完成搜索、详情、比价与预览；爬虫过程可实时直播，
撞风控或 DOM 改版时会自动恢复。

> ⚠️ **Agent 发动机尚未接入。** 原先对接的外部 CLI（Codex / Claude / OpenCode）已整体删除，
> 由自研实现取代。目前 `POST /v1/agent/**/run` 只回一个占位流（`error` + `runCompleted`），
> 不动任何真实数据。爬虫 / 账号 / 商品监控这些下游能力都在，等发动机接上即可跑通。

架构与分层约束见 [`AGENTS.md`](AGENTS.md)。

## Features

- **多平台爬虫** — 闲鱼 · 1688 · 小红书；1688 支持图搜 / 链接搜同款比价（销量最高 / 价格最低 / 严选）
- **步骤实时直播** — 采集过程推送截图帧，打开页、翻页、进详情全程可见
- **风控自动恢复** — 先自动过滑块；失败则弹有头窗口等人，Cookie 写回后从断点续跑
- **DOM 自动修复** — 厂家改版导致选择器失效时按字段指纹重定位，验证通过后热加载继续采
- **账号托管** — 扫码登录、登录态续期、多平台账号同屏
- **商品监控** — 把一批商品长期盯着，看卖不卖得掉、降没降价
- **本地一体** — 数据与浏览器会话跑在本机，不依赖远程爬虫 SaaS

## Screenshots

| 首页 | 爬虫过程 |
| :--: | :------: |
| <img src="./apps/web/public/home.png" width="320" alt="首页" /> | <img src="./apps/web/public/crawler.png" width="320" alt="爬虫" /> |

**爬虫工作台**：左侧 Agent 轨迹，中间步骤直播，右侧结构化结果（标题 / 价格 / 来源 / 详情）。

## Get Started

### 开发运行

```bash
pnpm install
pnpm prepare:python   # uv sync --frozen（仓库根 uv workspace）
pnpm tauri dev        # 桌面壳 + 前端

# 仅 Web 联调（默认 API http://127.0.0.1:8787）
pnpm dev
```

环境变量总表见 [`.env.example`](.env.example)。

## How it works

```text
用户一句话
    → Agent（发动机待接入）
    → 内置工具：search / product / compare / preview
    → Crawler（闲鱼 / 1688 / 小红书）
         ├─ 步骤直播截图 → 界面
         ├─ 风控 → 自动滑块 / 有头人工 → Cookie 回写
         └─ DOM 失效 → 指纹重定位 → 热加载
    → 结构化结果（价格 · 货源 · 利润对照）
```

## Repository

```text
apps/web/           Web 应用装配（React + Vite 根）
  └─ public/        品牌资源与截图（Vite publicDir，按 `/xxx` 引用）
packages/           前端 pnpm 工作区（见 packages/README.md）
  ├─ contracts/     与 Python 的线协议类型
  └─ client/        业务域包（ui-agent / ui-account / ui-ai / …）与机制包（runtime / app-state / routes）
packages-rs/        Rust workspace（成员包，见 packages-rs/README.md）
  └─ client/        Tauri 客户端（起停 Server、OS 能力）
packages-py/        Python uv workspace（见根 pyproject.toml）
  ├─ api/            FastAPI 装配与入口（`python -m api`）
  ├─ contracts/      零依赖线协议 DTO 与端口
  └─ …               core / infrastructure / browser / crawler / domains
```

更多目录说明见 [`AGENTS.md`](AGENTS.md)、[`packages/README.md`](packages/README.md)、
[`packages-rs/README.md`](packages-rs/README.md) 与 [`packages-py/api/src/api/README.md`](packages-py/api/src/api/README.md)。
