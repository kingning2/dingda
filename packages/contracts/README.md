# packages/contracts

前端与 Python Server 之间的**线协议类型**。纯类型，**零运行时**。

```text
account.ts         账号 / 扫码 / 登录态
agent-event.ts     产品 Agent 的事件流
agent-runtime.ts   外部 CLI Runtime（探测结果、安装进度）
ai-work.ts         AI 工作台
composer.ts        输入区
crawler.ts         采集
mcp.ts             MCP catalog
```

## 为什么单独成包

它是前端与 `server/` 之间**唯一**的共同语言。放独立包的目的不是复用，是**让越界可被发现**：
`server/src/contracts/` 改了字段，这里必须同步；而这里一旦 import 了 React 或任何运行时库，
就说明协议层被污染了 —— 那是可以直接看出来的信号。

## 边界

- 只放 `type` / `interface` / 字面量联合，**不放函数、不放常量、不放默认值**。
- 不 import 任何运行时依赖，尤其不 import React。
- 依赖方向：`contracts` 被所有前端包依赖，它自己不依赖任何前端包。

## 用法

按模块引，没有 barrel：

```ts
import type { AccountStatus } from "@v2/contracts/account";
```

不做 barrel 是刻意的：`export *` 遇到同名导出会**静默丢弃**，而协议里 `account` 与
`agent-runtime` 都有 `status` 这类通用名，barrel 会制造难以定位的消失。
