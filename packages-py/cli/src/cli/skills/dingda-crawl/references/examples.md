# Crawler Examples

所有示例统一调用 `scripts/run_tool.py`。复制命令后只替换业务参数、URL、图片地址和 `item_id`。

## 1. 爬取闲鱼搜索

```bash
"{{PYTHON}}" ".dingda-skills/dingda-crawl/scripts/run_tool.py" search \
  --platform xianyu --query "露营椅" --limit 30
```

读取重点：`item_id`、`title`、`price`、`desc`、`want_count`、`seller_nick`、`comments`。

## 2. 爬取闲鱼单条详情

```bash
"{{PYTHON}}" ".dingda-skills/dingda-crawl/scripts/run_tool.py" product \
  --platform xianyu --item-id "FROM_SEARCH"
```

`item-id` 必须来自 `search` 返回。详情缺失时不要用列表标题补写结论。

## 3. 爬取小红书搜索

```bash
"{{PYTHON}}" ".dingda-skills/dingda-crawl/scripts/run_tool.py" search \
  --platform xiaohongshu --query "露营椅" --limit 30
```

读取重点：`item_id`、`title`、`content_text`、`image_url`、`xsec_token`、`note_type`。

## 4. 爬取小红书图文详情

```bash
"{{PYTHON}}" ".dingda-skills/dingda-crawl/scripts/run_tool.py" product \
  --platform xiaohongshu --item-id "FROM_SEARCH" --xsec-token "FROM_SEARCH"
```

`note_type=video` 时详情会跳过。不要声称已经分析视频内容。

## 5. 爬取 1688 文本搜货

```bash
"{{PYTHON}}" ".dingda-skills/dingda-crawl/scripts/run_tool.py" search \
  --platform ali1688 --query "折叠露营椅" --limit 30
```

## 6. 爬取 1688 以图搜货

```bash
"{{PYTHON}}" ".dingda-skills/dingda-crawl/scripts/run_tool.py" search \
  --platform ali1688 --image "SOURCE_IMAGE_URL" --limit 30
```

`--image` 支持公开图片 URL 或本地图片路径。

## 7. 爬取 1688 链接找同款

```bash
"{{PYTHON}}" ".dingda-skills/dingda-crawl/scripts/run_tool.py" search \
  --platform ali1688 --url "SOURCE_PRODUCT_URL" --limit 30
```

## 8. 执行 1688 图像比价轮

```bash
"{{PYTHON}}" ".dingda-skills/dingda-crawl/scripts/run_tool.py" compare \
  --image "SOURCE_IMAGE_URL" --source 'SOURCE_CARD_JSON' --limit 20 --rounds 1
```

这一轮用于锁定视觉最接近的商品。不要把一轮结果当最终结论。

## 9. 执行 1688 文本比价轮

```bash
"{{PYTHON}}" ".dingda-skills/dingda-crawl/scripts/run_tool.py" compare \
  --query "折叠露营椅 承重120kg 带收纳袋" \
  --source 'SOURCE_CARD_JSON' --limit 20 --rounds 1
```

文本轮至少执行两次，分别使用硬约束和别名、场景或供给策略。

## 10. 拉起平台扫码登录

```bash
"{{PYTHON}}" ".dingda-skills/dingda-crawl/scripts/run_tool.py" login \
  --platform xianyu
```

仅当输出包含 `account.session_expired` 或 `account.cookie_required` 时调用。

## 11. 预览网页

```bash
"{{PYTHON}}" ".dingda-skills/dingda-crawl/scripts/run_tool.py" preview \
  --url "https://example.com/product" --title "商品预览"
```

`preview` 只推直播截图，不能替代 `search` 或 `product`。
