---
name: dingda-offer-verification
description: 验收 1688 比价候选，核对同款程度、价格口径、起订量、商家证据与风险，并给出首推、备选或淘汰结论。
---

# 1688 候选验收

所有证据与命令上下文都来自 `{{SERVER_DIR}}`。

## 输入

- `source_card`；
- 多轮 `compare` 返回的全部去重候选；
- 每轮策略、查询和新增候选记录。

## 资源文件

- 按 [assets/verification-report.md](assets/verification-report.md) 的表格记录验收结果。
- 硬门槛和排序规则读取 [references/scoring-policy.md](references/scoring-policy.md)。
- 候选补齐 `price_basis`、`quantity_included`、`shipping_cost`、
  `hard_constraint_mismatches` 后，必须运行：
  `"{{PYTHON}}" ".dingda-skills/dingda-offer-verification/scripts/score_offers.py" --input verification-input.json`
- `score_offers.py` 的 `accept` 是首推候选池，`conditional` 是备选池，`reject` 禁止推荐。

## 单项验收

对每个候选逐项核对：

1. **同款程度**：图片、标题、品牌/型号、关键尺寸或容量、材质、数量、配件是否一致。
2. **价格口径**：列表价是 SKU、阶梯价还是起批价；是否含运费；是否含配件；MOQ 是多少。
3. **商家证据**：供应商、销量、严选指数、商家评分、回头率。上游没返回的字段写 `unknown`。
4. **供货风险**：库存、起订量、定制、交期、退换、疑似盗图或标题堆词。
5. **价格可比性**：统一到单件到手价后再比较，不要拿总价和单件价直接比。

归一化公式：

```text
单件到手价 = (商品价 + 可确认运费 + 必要配件) / 实收数量
```

运费或 SKU 不明确时，只能给区间或标记 `conditional`。

## 判定

- `accept`：硬约束全部匹配，价格口径明确，商家证据足以支撑推荐。
- `conditional`：同款可信，但价格、运费、MOQ 或商家字段有缺项。
- `reject`：任一硬约束不匹配、同款证据弱、价格口径误导或明显复制来源图。

禁止规则：

- `merchant_rating=null` 不等于高分；
- 销量高不等于同款；
- 最低标价不等于最低到手价；
- 没有来源卡逐项对照时不能给 `accept`。

## 最终比较

先筛掉 `reject`，再按以下顺序给出结论：

1. 硬约束匹配度；
2. 单件到手价及价格口径确定性；
3. 商家评分、回头率、销量等可靠性证据；
4. 供货与起订风险；
5. 与来源商品的价差和利润空间。

最终输出：

- **首推**：最适合的来源替代货源；
- **备选**：价格更低但风险更高，或质量证据更强但价格更高；
- **淘汰**：至少给出一个明确淘汰原因；
- **未知项**：运费、SKU、评分、交期等。

如果三轮后仍没有 3 个 `accept` 或 `conditional` 候选，结论写“样本不足”，不要强行推荐。
