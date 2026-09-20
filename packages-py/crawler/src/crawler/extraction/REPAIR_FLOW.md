# DOM 自动修复：现状

多平台（闲鱼 / 小红书）DOM 自动修复的**现状快照**：编排链路、设计取舍、已知短板。

> 本文原先记录的是「指纹 + AI 补丁」两轮链路。AI 补丁轮（`cli/repair/propose.py`、
> `run_cli`）随外部 CLI 对接一并删除，现在**只剩指纹重定位一轮**：抽不到就判失败。
> 下面描述的是删除后的状态。

---

## 一、编排链路（现状）

```mermaid
flowchart TD
    IN["抓取入口<br/>crawler.search / crawler.detail"] --> RISK{"命中风控?<br/>channel.risk / crawler.blocked"}
    RISK -- "是" --> R1["run_step 步骤级恢复<br/>渠道: 自动滑块 → 有头人工窗"]
    R1 --> R2["重试该步"] --> RISK
    RISK -- "否" --> AUTH{"登录失效?<br/>account.session_expired<br/>account.cookie_required"}
    AUTH -- "是" --> A1["with_crawl_recovery<br/>run_login 扫码"]
    A1 --> A2["重试整次调用 max_auth=2"] --> AUTH
    AUTH -- "否" --> DOMOK{"抽取成功?"}
    DOMOK -- "是" --> OUT["返回 CrawlItem"]
    DOMOK -- "否 / 选择器失效" --> HOOK["repair_detail_dom 编排起点"]

    HOOK --> GATE{"gates<br/>开关 / 平台锁"}
    GATE -- "拒" --> GERR["error = disabled / busy"]
    GERR --> RAISE["raise_repair_error"]
    GATE -- "准" --> DUMP["dump_dom_tree<br/>采集 tag / class / text 精简树"]
    DUMP --> RISKTXT{"页面文本像风控?"}
    RISKTXT -- "是" --> RTERR["error = channel.risk"] --> RAISE
    RISKTXT -- "否" --> FP["指纹 relocate_section<br/>~/.dingda/v2/dom_fingerprints.json"]
    FP -- "命中" --> VAL["adapter.evaluate_extract<br/>跑平台自己的抽取 JS"]
    FP -- "未命中" --> AERR["error = dom_repair_failed"] --> RAISE
    VAL -- "通过" --> PERSIST
    VAL -- "不通过" --> AERR

    PERSIST["persist_patch<br/>write_extract_section 原子写回 + 热加载"]
    PERSIST --> FPSAVE["save_fingerprint 存字段指纹"] --> OK["RepairResult ok<br/>用修复后 payload 继续"]
    RAISE --> FAIL["AppError<br/>channel.risk / account.session_expired / crawler.dom_repair_*"]
```

关键设计：**验证器就是平台自己的抽取脚本**。指纹给出的选择器必须让 `DETAIL_DOM_JS` /
`DOM_DETAIL_JS` 真的抽出内容（`adapter.payload_ok`）才算通过；通过后写回
`extract.json` 并落指纹，下次同类 DOM 变化可直接命中指纹、不必再推理。

`orchestrator.py` 结束时 `release_platform()`，平台锁保证同一平台不会并发修复。

---

## 二、真机修掉的两个坑（设计由此而来）

### ① `dump_roots()` 只给一个根 → 卖家区被截掉

`adapter.dump_roots()` 原来只返回 `item-main-container`（+ `body` 兜底）。卖家区是它的
**兄弟**节点，从 `body` 数下来是第 7 层，超过 `maxDepth=6` → 昵称/简介元素被整片截掉，
精简树里根本没有。

所以 `sources/xianyu/repair_adapter.py` 的 `dump_roots()` 把
`[class*="item-user-container"]` 也当根（子树从浅层展开），`body` 留作兜底。
**新增平台适配器时注意**：dump 根要覆盖所有会被抽字段的子树，别只给主容器。

### ② `title_noise` 没盖住站点默认标题

选择器空掉后 `DOM_DETAIL_JS` 会兜底取 `document.title`，于是
`小红书 - 你的生活兴趣社区` 被当成正常笔记标题接受，修复闸门因此不触发。
解法：把站点默认标题加进 `extract.json` 的 `title_noise`。

---

## 三、已知短板

- **指纹未命中即失败**：AI 补丁轮删除后没有兜底。首见的新 DOM 结构必须有人补
  `extract.json`，或实现自己的补丁发动机再接回来。
- **`gates` 里的 AI 预算形同虚设**：`consume_ai_budget()` / `max_rounds()` 仍在，
  但已无调用方；`DINGDA_DOM_REPAIR_ROUNDS` / `DINGDA_DOM_REPAIR_BUDGET` 两个环境变量
  目前不产生任何效果。
- **`bridge.py` / `DomSnapshot` 仅剩测试在用**：`api/tests/crawler/test_repair_bridge.py`
  还覆盖着，产品路径已不经过它们。
