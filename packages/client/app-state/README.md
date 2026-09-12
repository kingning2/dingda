# packages/client/app-state

跨域共享 UI 状态的唯一来源：启动探测结果（Agent CLI 运行时 / 平台账号 / 最近会话）。

包名 `@v2/app-state`。

## 为什么单独成包

这三份状态天然跨域 —— Agent 域写 `agents`、账号域写 `accounts`、首页域读 `recentWorks`。
它原本挂在 `ui-crawler` 里，于是「谁都要引 ui-crawler」和「ui-crawler 要引 ui-agent」
同时成立，依赖图被拧成环，`@v2/runtime` 也被迫反向依赖业务包。

状态本身不依赖任何业务逻辑，只依赖线协议类型，所以下沉为**叶子包**：
各域各自向上依赖它，环与反向依赖同时消失。

## 文件

- `src/discovery-store.ts` —— zustand store（`useDiscoveryStore`）与 `ACCOUNT_PLATFORMS`
- `src/index.ts`

## 依赖

- 工作区：`@v2/contracts`
- 外部：`zustand`
- peer：`react`

**不要往这里加业务依赖。** 一旦引入 `@v2/ui-*`，它就不再是叶子，环会立刻回来。
谁负责「写」状态，谁留在自己的域里：

- Agent 侧写入 → `@v2/ui-agent/agent-runtime-scan`
- 账号侧写入 → `@v2/ui-account/account-discovery`
- 需要「两边一起做」的启动编排 → `apps/web/src/boot`

## 边界

改本包前先看仓库根的 [AGENTS.md](../../../AGENTS.md) 与
[.agents/skills/layers.md](../../../.agents/skills/layers.md)。
