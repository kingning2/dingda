# DingDa CLI Reference

所有命令都在会话根目录（`.dingda-skills/` 所在处）执行，统一入口为
`{{ENTRY}}`。参数使用连字符形式，例如 `--item-id`、`--proxy-url`。

## Common result contract

```json
{
  "ok": true,
  "items": [],
  "error_code": null,
  "message": null
}
```

- `ok=true`：读取 `items`、`item` 或 `source` 等对应字段。
- `ok=false`：先处理 `error_code`，不要继续基于空结果下结论。
- 所有命令的输出都是 JSON，stderr 才是日志。

## search

用途：在闲鱼、小红书或 1688 建立样本池。

```bash
{{ENTRY}} search --platform xianyu --query "关键词" --limit 30
{{ENTRY}} search --platform xiaohongshu --query "关键词" --limit 30
{{ENTRY}} search --platform ali1688 --query "关键词" --limit 30
{{ENTRY}} search --platform ali1688 --image "图片 URL 或本地路径" --limit 30
{{ENTRY}} search --platform ali1688 --url "1688/淘宝/天猫链接或 ID" --limit 30
```

常用参数：

| 参数 | 说明 |
|------|------|
| `--platform` | `xianyu`、`xiaohongshu` 或 `ali1688` |
| `--query` | 搜索词；闲鱼和小红书必填 |
| `--image` | 1688 以图找货，本地路径或 URL |
| `--url` | 1688 链接找同款 |
| `--limit` | 返回数量，建议 20 到 50 |
| `--sort` | `price_asc`、`price_desc`、`sold_desc`、`yx_desc` |
| `--score-level` | `high`、`medium` 或 `low` |
| `--purchase-amount` | 1688 采购件数 |
| `--cookie` | 可选登录 cookie |
| `--proxy-url` | 可选代理 URL |
| `--cookie-domain` | cookie 注入域名 |

## product

用途：补拉单条商品或笔记详情。

```bash
{{ENTRY}} product --platform xianyu --item-id "FROM_SEARCH"
{{ENTRY}} product --platform xiaohongshu --item-id "FROM_SEARCH" --xsec-token "FROM_SEARCH"
```

常用参数：

| 参数 | 说明 |
|------|------|
| `--platform` | `xianyu` 或 `xiaohongshu` |
| `--item-id` | 必须来自 `search` 返回 |
| `--cookie` | 可选登录 cookie |
| `--xsec-token` | 小红书详情 token |
| `--proxy-url` | 可选代理 URL |

## browse

用途：连贯浏览——打开搜索列表后，在同一个浏览器页里一个一个点进商品详情
（详情 → 返回列表 → 下一个），画面是连续的一段。需要实地看几款商品长什么样、
或核对详情与列表是否一致时用；只想快速建样本池仍用 `search`。

```bash
{{ENTRY}} browse --platform xianyu --query "关键词" --limit 8 --detail-count 3
```

常用参数：

| 参数 | 说明 |
|------|------|
| `--platform` | 目前仅 `xianyu`；`ali1688` 无页面可逛 |
| `--query` | 搜索词 |
| `--limit` | 列表条数，默认 10 |
| `--detail-count` | 要逐个点开几条详情，默认 3，上限 10 |
| `--cookie` | 可选登录 cookie |
| `--proxy-url` | 可选代理 URL |

耗时：每条详情约 15 到 25 秒，`--detail-count 3` 通常 1 到 2 分钟。

## compare

用途：根据来源商品在 1688 找同款并返回候选。

```bash
{{ENTRY}} compare --image "SOURCE_IMAGE_URL" --source 'SOURCE_CARD_JSON' --limit 20 --rounds 1
{{ENTRY}} compare --url "SOURCE_URL" --source 'SOURCE_CARD_JSON' --limit 20 --rounds 1
{{ENTRY}} compare --query "硬约束关键词" --source 'SOURCE_CARD_JSON' --limit 20 --rounds 1
```

常用参数：

| 参数 | 说明 |
|------|------|
| `--image` | 来源商品图片 |
| `--url` | 来源商品链接 |
| `--source` | `source_card` JSON |
| `--query` | 本轮独立查询词 |
| `--limit` | 候选数量，建议 20 |
| `--rounds` | 单轮调用固定为 `1` |
| `--sort` | 候选排序策略 |
| `--score-level` | 相关性等级 |
| `--purchase-amount` | 采购件数 |
| `--tags` | 1688 TC 品池标签 |
| `--ic-tags` | 1688 IC 品池标签 |

## login

用途：登录失效后拉起扫码并阻塞等待。

```bash
{{ENTRY}} login --platform xianyu
{{ENTRY}} login --platform xiaohongshu
{{ENTRY}} login --platform ali1688
```

只在工具返回 `account.session_expired` 或 `account.cookie_required` 时调用。扫码完成后重试原命令。

## preview

用途：打开已确认的完整 URL，并向前端推送浏览器直播截图。

```bash
{{ENTRY}} preview --url "https://example.com/product" --title "商品预览"
```

常用参数：

| 参数 | 说明 |
|------|------|
| `--url` | 必须是完整 `http(s)` URL |
| `--title` | 可选展示标题 |
| `--duration-s` | 停留秒数，范围 2 到 30 |

`preview` 不解析商品，不替代 `search` 或 `product`。

## Help

查看当前注册的全部工具和参数：

```bash
{{ENTRY}} --help
{{ENTRY}} search --help
{{ENTRY}} compare --help
```
