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

## 头条搜索站长平台

1. 打开 [zhanzhang.toutiao.com](https://zhanzhang.toutiao.com/)，添加站点 `https://kingning2.github.io/dingda/`
2. 选择 **HTML 标签验证**，复制 `content` 值
3. 在 GitHub 仓库 Settings → Secrets → Actions 添加 `TOUTIAO_SITE_VERIFICATION`（重新部署后 meta 生效）

或使用 **文件验证**：将平台下载的文件重命名为 `ByteDanceVerify.html`，放到 `website/public/`，部署后访问 `https://kingning2.github.io/dingda/ByteDanceVerify.html`

验证通过后提交 sitemap：`https://kingning2.github.io/dingda/sitemap.xml`
