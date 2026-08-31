# DingDa Server

多用户电商选品 / 市场快照 / 利润分析后端。

## 架构原则

```text
客户端上传：我看到了什么
Server 保存：市场历史上发生过什么
Server 计算：这个商品赚不赚钱（Profit Engine 预留）
Server 分析：这个商品有没有机会（后续实现）
```

全局商品数据（`products`、`product_platforms`、各类 `*_snapshots`）**不绑定 workspace**。  
用户/租户数据（`discovery_tasks`、`crawl_tasks`、`product_watch`、`product_costs`、`opportunities` 等）**绑定 workspace**。

## 快速启动

```bash
cd apps/server
docker compose up -d --build
```

## 认证

```bash
# 注册（自动创建默认 workspace）
curl -X POST http://localhost:8080/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"demo@example.com","password":"password123","name":"Demo"}'

# 登录
curl -X POST http://localhost:8080/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"demo@example.com","password":"password123"}'
```

# 创建爬取任务（可选，batch 上传也会自动 upsert crawl_id）

```bash
curl -X POST http://localhost:8080/api/v1/crawl-tasks \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"client_ref":"crawl_xxx","platform":"ali1688"}'
```

## 查询

```bash
# 平台商品列表（全局去重后的 product_platforms）
curl "http://localhost:8080/api/v1/product-platforms?platform=ali1688&limit=20" \
  -H "Authorization: Bearer <token>"

# 某平台商品的历史快照
curl "http://localhost:8080/api/v1/snapshots?product_platform_id=1&limit=20" \
  -H "Authorization: Bearer <token>"
```

## 批量上传 Snapshot

```bash
curl -X POST http://localhost:8080/api/v1/snapshots/batch \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "crawl_id": "crawl_xxx",
    "snapshots": [
      {
        "snapshot_id": "snap_001",
        "platform": "ali1688",
        "captured_at": "2026-08-29T17:00:00+08:00",
        "product": {
          "platform_product_id": "123456",
          "title": "无线充电器",
          "url": "https://detail.1688.com/offer/123456.html"
        },
        "pricing": {
          "price": 18.5,
          "original_price": 25.0,
          "price_text": "¥18.5"
        },
        "sales": {
          "sales_text": "月销5000+"
        },
        "raw": {
          "data": {"source": "client"},
          "data_version": "v1"
        }
      }
    ]
  }'
```

Server 处理流程：

1. 校验 + 解析 `crawl_id` → `crawl_tasks`
2. `UNIQUE(platform, platform_product_id)` 查找/创建 `product_platforms`
3. 计算 `snapshot_hash`，幂等去重
4. 单事务写入 `product_snapshots` 及子表（price/sales/sku/seller/shipping/media/raw）

## 数据库表（19 张）

| 分类 | 表 |
|------|-----|
| 用户/租户 | `users`, `workspaces`, `workspace_members` |
| 全局商品 | `products`, `product_platforms`, `product_snapshots`, `price_snapshots`, `sales_snapshots`, `sku_snapshots`, `seller_snapshots`, `shipping_snapshots`, `product_media_snapshots`, `raw_snapshots` |
| 采集任务 | `discovery_tasks`, `crawl_tasks` |
| 用户业务 | `product_watch`, `product_costs`, `opportunities` |
| 分析（预留） | `profit_analysis`, `market_analysis` |

Migration：`migrations/003_market_schema.sql`

## 代码结构

```text
src/
  error.rs         # 统一错误类型 + JSON 响应格式
  middleware/      # 请求上下文（request_id）+ 访问日志
  extractors/      # ApiJson 等统一提取器
  models/          # Entity + DTO
  repo/            # 数据库访问
  services/        # Snapshot Ingestion
  engine/profit.rs # Profit Engine 占位
  routes/          # HTTP API
```

## 统一错误响应

所有 API 错误（含 404、鉴权失败、JSON 解析失败）返回同一 JSON 结构：

```json
{
  "error": {
    "code": "BAD_REQUEST",
    "message": "invalid email",
    "request_id": "550e8400-e29b-41d4-a716-446655440000"
  }
}
```

`code` 取值：`BAD_REQUEST` | `UNAUTHORIZED` | `NOT_FOUND` | `CONFLICT` | `INTERNAL_ERROR`

客户端可传入 `X-Request-Id` 头；未传时服务端自动生成，并在响应头 `X-Request-Id` 中回传，便于日志关联。

## 中间件

`middleware::apply()` 在 `main.rs` 中挂载，顺序为：

1. **request context** — 生成/透传 `request_id`，写入 task-local 供错误响应使用
2. **access log** — 记录 method、path、status、耗时；4xx 打 warn，5xx 打 error

Handler 返回 `AppResult<T>`，提取器（如 `ApiJson`、`AuthUser`）的 `Rejection` 也统一为 `AppError`。

## 环境变量

见 `.env.example`。生产环境务必修改 `JWT_SECRET`。
