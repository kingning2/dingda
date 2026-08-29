# @dingda/website

叮答官网 + 控制台演示（方案 A 骨架），基于 [NextAdmin](https://github.com/NextAdminHQ/nextjs-admin-dashboard) UI 二开。

## 本地开发

```bash
cd website
pnpm install --ignore-workspace
pnpm dev
```

| 地址 | 说明 |
|------|------|
| http://localhost:3200 | 营销首页 |
| http://localhost:3200/console | 工作台（骨架） |

## 控制台路由（1:1 对齐桌面 L1）

| 路由 | 桌面端 | 当前状态 |
|------|--------|----------|
| `/console` | `/dashboard` | 7 区块 Bento + 统计卡（演示数据） |
| `/console/discovery/*` | `/discovery/*` | 机会表 + 开始选品表单 |
| `/console/products` | `/products` | 商品库表 |
| `/console/profit/*` | `/profit/*` | 表单骨架 |
| `/console/monitoring/*` | `/monitoring/*` | 占位骨架 |
| `/console/tasks` | `/tasks` | Agent 任务表 |
| `/console/settings/*` | `/settings/*` | 设置骨架 |

后续对接桌面端时，见 `src/lib/desktop-ports.ts` 与 `src/content/business.ts` 中的 MOCK 数据。

## 构建

```bash
pnpm build
pnpm build:pages    # GitHub Pages（/dingda 子路径）
```
