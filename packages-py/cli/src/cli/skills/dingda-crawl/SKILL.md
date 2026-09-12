---
name: dingda-crawl
description: 在闲鱼、小红书和 1688 上执行真实浏览器选品取证。用于找货、看行情、比价、看内容风向、补商品详情或预览网页；结论必须来自命令行返回的真实数据。
triggers:
  - "闲鱼选品"
  - "小红书风向"
  - "1688 比价"
  - "找同款"
  - "商品详情"
  - "预览网页"
---

# DingDa Crawl

通过叮答命令行工具获取真实商品、笔记和比价证据。所有结论必须能追溯到本次命令返回的数据；爬取失败就明确说明失败，不要凭记忆补商品。

## Resource map

```text
dingda-crawl/
├── SKILL.md
├── agents/openai.yaml
├── scripts/run_tool.py
└── references/
    ├── cli-reference.md
    ├── evidence-policy.md
    └── examples.md
```

- 开始调用工具前读取 [references/cli-reference.md](references/cli-reference.md)。
- 形成选品结论或进入比价链路前读取 [references/evidence-policy.md](references/evidence-policy.md)。
- 不确定某类平台或工具怎么调用时，读取 [references/examples.md](references/examples.md)。

## When to use this skill

使用本 Skill：

- 在闲鱼搜索商品，了解真实货盘、价格、卖家、描述和留言。
- 在小红书搜索内容，判断品类热度、使用场景和内容风向。
- 在 1688 搜索货源或执行同款比价。
- 根据搜索结果补拉单条商品详情。
- 登录失效后拉起扫码登录。
- 把已找到的网页推送到叮答前端预览。

不要使用本 Skill：

- 把列表标题当成完整商品证据。
- 用一次搜索直接得出选品或比价结论。
- 用 `preview` 代替结构化搜品。
- 凭历史记忆生成不存在的 `item_id`、价格、销量或链接。

## Runtime contract

- 工作目录：会话根目录（`.dingda-skills/` 所在处，命令中的相对路径以此为基准）
- 工具入口：`"{{PYTHON}}" ".dingda-skills/dingda-crawl/scripts/run_tool.py"`
- stdout：纯 JSON。成功先读 `ok=true`，失败先读 `error_code` 和 `message`。
- 日志：stderr，不要把日志混入 JSON 解析。
- 浏览器工具会真实打开页面，单次通常需要 1 到 5 分钟。
- shell timeout 至少设置为 `300000 ms`。

## Examples

平台和工具的逐项示例统一收在
[references/examples.md](references/examples.md)，包含：

1. 爬取闲鱼搜索。
2. 爬取闲鱼单条详情。
3. 爬取小红书搜索。
4. 爬取小红书图文详情。
5. 爬取 1688 文本搜货。
6. 爬取 1688 以图搜货。
7. 爬取 1688 链接找同款。
8. 执行 1688 图像比价轮。
9. 执行 1688 文本比价轮。
10. 拉起平台扫码登录。
11. 预览网页。

## Workflow

### Step 1: 选择证据入口

| 目标 | 工具 | 主要输出 |
|------|------|----------|
| 建样本池 | `search` | 商品/笔记列表与详情字段 |
| 核单条商品 | `product` | `desc`、`comments`、`want_count`、卖家等 |
| 1688 同款比价 | `compare` | 价格、销量、供应商、评分、轮次与推荐依据 |
| 处理登录失效 | `login` | 用户扫码后的账号状态 |
| 给用户看网页 | `preview` | 页面标题、最终 URL、直播帧数量 |

### Step 2: 搜索真实样本

闲鱼：

```bash
"{{PYTHON}}" ".dingda-skills/dingda-crawl/scripts/run_tool.py" search --platform xianyu --query "露营椅" --limit 30
```

小红书：

```bash
"{{PYTHON}}" ".dingda-skills/dingda-crawl/scripts/run_tool.py" search --platform xiaohongshu --query "露营椅" --limit 30
```

1688 文本找货：

```bash
"{{PYTHON}}" ".dingda-skills/dingda-crawl/scripts/run_tool.py" search --platform ali1688 --query "折叠露营椅" --limit 30
```

1688 以图找货：

```bash
"{{PYTHON}}" ".dingda-skills/dingda-crawl/scripts/run_tool.py" search --platform ali1688 --image "https://example.com/product.jpg" --limit 30
```

1688 链接找同款：

```bash
"{{PYTHON}}" ".dingda-skills/dingda-crawl/scripts/run_tool.py" search --platform ali1688 --url "https://detail.1688.com/offer/123456789.html" --limit 30
```

选品调研要多轮换词并累计样本。闲鱼优先看 `desc`、`comments`、`want_count` 和卖家；小红书优先看 `content_text`，视频笔记跳过详情。

### Step 3: 补拉单条详情

闲鱼：

```bash
"{{PYTHON}}" ".dingda-skills/dingda-crawl/scripts/run_tool.py" product --platform xianyu --item-id "FROM_SEARCH"
```

小红书图文：

```bash
"{{PYTHON}}" ".dingda-skills/dingda-crawl/scripts/run_tool.py" product --platform xiaohongshu --item-id "FROM_SEARCH" --xsec-token "FROM_SEARCH"
```

`item_id` 必须来自 `search` 返回。没有详情时，不要把列表标题扩写成商品结论。

### Step 4: 处理登录失效

当输出包含 `account.session_expired` 或 `account.cookie_required`：

```bash
"{{PYTHON}}" ".dingda-skills/dingda-crawl/scripts/run_tool.py" login --platform xianyu
```

登录命令会阻塞并等待用户扫码。登录成功后立即重试原命令。

### Step 5: 执行比价链路

涉及同款、1688 拿货价或利润时，必须按以下顺序执行：

```text
dingda-source-evidence
  -> dingda-price-compare
  -> dingda-offer-verification
```

`dingda-price-compare` 至少执行三轮不同策略，且每轮显式传入 `--rounds 1`。第一轮用图像，第二轮用硬约束文本，第三轮换别名、场景或供给策略。

图像轮示例：

```bash
"{{PYTHON}}" ".dingda-skills/dingda-crawl/scripts/run_tool.py" compare --image "SOURCE_IMAGE_URL" --source 'SOURCE_CARD_JSON' --limit 20 --rounds 1
```

文本轮示例：

```bash
"{{PYTHON}}" ".dingda-skills/dingda-crawl/scripts/run_tool.py" compare --query "折叠露营椅 承重120kg 带收纳袋" --source 'SOURCE_CARD_JSON' --limit 20 --rounds 1
```

### Step 6: 预览网页

只有已经拿到目标 URL、需要让用户看到页面时才调用：

```bash
"{{PYTHON}}" ".dingda-skills/dingda-crawl/scripts/run_tool.py" preview --url "https://example.com/product" --title "商品预览"
```

`preview` 只负责打开和直播截图，不能替代 `search` 或 `product`。

## Output contract

最终交付必须包含本次实际使用的入口和证据：

1. 查询平台、关键词或 URL。
2. 实际返回的样本数量。
3. 关键商品字段及对应 `item_id`。
4. 失败、跳过和未知项。
5. 若进入比价链路，附多轮记录、候选验收和来源卡。

不得声称“已全量抓取”或“平台所有商品都看过了”。只能描述本次实际执行的轮次和样本。

## Guardrails

- 闲鱼是货盘真相，小红书用于内容风向，1688 用于货源和比价。
- 结论必须基于详情字段，不能只看搜索列表标题。
- 缺少 `cookie` 时先处理登录，不要反复重试同一个失效命令。
- 标签异常时结合 URL、卖家和详情判断，不把保障文案当商品名。
- 任何数字都必须来自工具输出；没有拿到就写 `unknown`。
- 不编造 `item_id`、URL、价格、销量、评价或供应商。

## Handoff

- 只有关键词：先 `search`，形成来源商品后再进入比价。
- 有单条商品：先 `product` 核详情，再交给 `dingda-source-evidence`。
- 已形成 `source_card`：交给 `dingda-price-compare`。
- 已拿到候选：交给 `dingda-offer-verification`。
