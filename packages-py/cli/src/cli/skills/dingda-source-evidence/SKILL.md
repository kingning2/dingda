---
name: dingda-source-evidence
description: 在 1688 同款比价前锁定来源商品的硬约束、价格口径和待确认字段；来源不清楚时禁止直接找同款。
---

# 来源商品证据

所有命令必须在会话根目录（`.dingda-skills/` 所在处）下执行。

## 目标

把用户给的闲鱼、小红书、淘宝或 1688 商品整理成一份可复核的 `source_card`。
后续比价轮次必须复用这张卡，不能只记一句标题。

## 来源不完整时先补证据

- 只有关键词时，先用 `{{ENTRY}} search --platform xianyu --query "..." --limit 20` 找来源；
  不要直接把关键词当来源商品。
- 只有链接或 `item_id` 时，优先用 `{{ENTRY}} product --platform xianyu --item-id "..."` 核详情。
- 图片、标题、价格、卖家或规格缺失时，标记为 `unknown`，不要猜。
- 来源商品至少要有 `platform + item_id/url + title + image_url` 才能进入比价。

## 资源文件

- 先用 [assets/source-card.json](assets/source-card.json) 建立结构。
- 原始商品 JSON 用脚本归一化：
  `"{{PYTHON}}" ".dingda-skills/dingda-source-evidence/scripts/normalize_source.py" --input raw-source.json`
- 字段是否有资格成为硬约束，读取 [references/source-card-rules.md](references/source-card-rules.md)。
- `ok=false` 时先补缺失证据，不要继续比价。

## source_card

输出并持续维护以下结构：

```json
{
  "item_id": "xy-1001",
  "platform": "xianyu",
  "url": "https://www.goofish.com/item?id=xy-1001",
  "title": "几乎全新露营椅 承重120kg",
  "image_url": "https://...",
  "price": "89",
  "price_basis": {
    "quantity_included": 1,
    "condition": "used",
    "shipping": "unknown",
    "bundle": "unknown"
  },
  "seller": "山系玩家",
  "hard_constraints": ["折叠露营椅", "承重120kg", "带收纳袋"],
  "soft_preferences": ["黑色"],
  "unknowns": ["运费是否包含", "具体面料"]
}
```

## 字段判断规则

- `hard_constraints`：缺失会导致明显不同款的品牌/型号、尺寸、容量、材质、数量、配件和成色。
- `soft_preferences`：颜色、风格、卖家地区等可替代项。
- 价格必须写清口径：单件价、总价、是否含运费、是否含配件、二手成色。
- 没有拿到详情时，`price_basis` 的未知项写 `unknown`，不要按标题推断。
- 来源价格用于计算价差时必须保留原字符串和归一化单价。

## 交接

完成后把 `source_card` 交给 `dingda-price-compare`。
如果没有形成合法 `source_card`，停止比价并明确缺什么证据。
