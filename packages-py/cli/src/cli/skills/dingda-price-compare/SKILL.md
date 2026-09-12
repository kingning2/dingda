---
name: dingda-price-compare
description: 对已锁定的来源商品执行至少三轮不同策略的 1688 同款比价并汇总证据；禁止一次搜索后直接下结论。
---

# 多轮 1688 比价

所有命令必须在会话根目录（`.dingda-skills/` 所在处）下执行。

## 强制依赖

1. 先使用 `dingda-source-evidence`，拿到合法 `source_card`。
2. 每轮搜索都传同一个 `--source '<source_card JSON>'`。
3. 所有候选在出结论前必须交给 `dingda-offer-verification` 验收。

缺少来源卡或验收步骤时，不允许给最终推荐。

## 不可跳过的轮次

至少执行 **3 轮成功返回** 的搜索，且每轮必须使用不同策略。
`--rounds 1` 是刻意设置：由你明确控制每一轮的查询，不要依赖单个 Tool 内部扩词代替多轮。

### 第 1 轮：图像同款

```bash
{{ENTRY}} compare --image "SOURCE_IMAGE_URL" --source 'SOURCE_CARD_JSON' --limit 20 --rounds 1
```

目的：锁定视觉最接近的商品。记录 `item_id`、价格、匹配度、供应商、销量和商家评分。

### 第 2 轮：硬约束文本

从来源标题和 `hard_constraints` 组合查询，不要复制整段营销标题：

```bash
{{ENTRY}} compare --query "核心品类 + 品牌/型号 + 关键规格" --source 'SOURCE_CARD_JSON' --limit 20 --rounds 1
```

示例：`折叠露营椅 承重120kg 带收纳袋`。

### 第 3 轮：别名、场景或供给策略

换一个语义角度，不能只是调换词序：

```bash
{{ENTRY}} compare --query "别名 + 使用场景 + 材质/尺寸" --source 'SOURCE_CARD_JSON' --limit 20 --rounds 1
```

示例：`月亮椅 户外钓鱼 铝合金 可折叠`。

### 继续加轮

满足任一条件就继续第 4 轮：

- 三轮去重后少于 6 个可比较候选；
- 前三轮最高价与最低价差异明显，但缺规格解释；
- 关键候选的商家评分、销量或价格口径缺失；
- 来源商品本身存在品牌/型号/成色歧义。

第 4 轮优先补缺口，例如“品牌 + 型号”“工厂/现货/代发”“尺寸 + 材质”，不要重复前三轮。

## 资源文件

- 每轮结果复制 [assets/round-record.json](assets/round-record.json) 的结构记录。
- 三轮完成后必须运行：
  `"{{PYTHON}}" ".dingda-skills/dingda-price-compare/scripts/validate_rounds.py" --input round-record.json`
- `ok=false` 时禁止进入候选验收；按 `errors` 补轮。
- 轮次为什么必须不同、何时继续加轮，读取 [references/multiround-policy.md](references/multiround-policy.md)。

## 每轮记录

为每轮保留：

```json
{
  "round": 1,
  "strategy": "image",
  "query": "",
  "returned": 20,
  "new_unique": 16,
  "candidate_ids": ["..."],
  "notes": "视觉最接近"
}
```

所有轮次按 `item_id` 去重。后续轮次发现同一商品时，合并更完整的字段，不要把重复商品算成新增证据。

## 放行条件

给最终结论前同时满足：

- 至少 3 个成功轮次，且至少包含 1 轮图像检索和 1 轮文本检索；
- 每轮搜索词或策略有实质差异；
- 候选已按来源卡过滤，明确排除规格不符项；
- 已读取 `dingda-offer-verification` 的验收结果；
- 推荐理由同时覆盖价格、同款匹配和商家可靠性。

证据不足时直接说明缺哪一类证据和已完成的轮次，不要用低价单独拍板。

## 输出

最终回答必须包含：

1. 来源商品与硬约束；
2. 多轮检索表（轮次、策略、查询、新增候选）；
3. 1688 对比表（价格口径、起订量、匹配度、销量、商家评分/未知）；
4. 首推、备选、淘汰项及理由；
5. 置信度和仍缺失的证据。

不要声称“已经全量比价”。只能描述本次实际轮次和样本。
