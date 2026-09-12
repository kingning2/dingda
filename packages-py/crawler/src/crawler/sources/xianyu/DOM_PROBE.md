# 闲鱼详情 DOM 探测记录

探测日期：2026-09-10  
样本商品：`https://www.goofish.com/item?id=1027680267393`  
脚本：

- `packages-py/api/scripts/probe_xianyu_detail_dom.py` — 过滑块 + 扫 DOM 候选
- `packages-py/api/scripts/probe_xianyu_detail_struct.py` — **拉主区 HTML/DOM 树并分析节点**
- 产物目录：`packages-py/api/tmp/xianyu_detail_dom_probe/`（`struct.json` = 结构分析结果）

固化配置：`extract.json` → `detail_dom`；运行时：`DETAIL_DOM_JS`（mtop / `lib.mtop` 失败后兜底）。

---

## 核心做法：拿结构 → 分析节点 → 定选择器

就是「获取页面结构，再分析出对应 DOM 节点」，不是凭空猜 class。

闲鱼是 SPA：`view-source` / 首包 HTML 几乎没有商品字段，字段在浏览器里渲染进 DOM。  
所以「获取 HTML 结构」在这里等于：

1. Camoufox 打开真实商品页（Cookie + 过滑块）
2. `page.evaluate` 读**已渲染 DOM 树**（等价于 DevTools Elements 里看到的结构）
3. 按父子关系 dump 每个容器的 `tag / class / innerText / children`
4. 对照页面上能看见的「价格 / 想要 / 正文 / 卖家」文案，把字段落到具体节点
5. class 带 CSS Modules 哈希（`price--OEWLbcxC`）时，收成稳定的 `[class*="price"]` 写进 `extract.json`

关键产物是 `struct.json`：主信息区每个子节点的 class 与文案，选择器是对着这棵树定的。

---

## 完整步骤

### 1. 注入登录 Cookie，Camoufox 打开商品页

与产品 crawler 相同：账号库闲鱼 cookie → `to_browser_cookies` → `CamoufoxAdapter.open`。  
无 `item_id` 时可先搜关键词，从 `a[href*="/item?id="]` 取首条。

### 2. 必须先过百信滑块

不过滑块时主区是骨架，DOM 里只有推荐流（`feeds-*`），分析出来的节点是错的。  
做法：`try_solve_slider(..., prefer_page_mouse=True)`，成功后再打开详情并等待主区有字。

### 3. 获取主区 DOM 结构并分析

`probe_xianyu_detail_struct.py` 对下列根做 **children dump**（最终结论以结构为准）：

- `[class*="item-main-info"]` — 右侧信息区整棵子树
- `[class*="desc"]` / `want` / `price` / `value` — 字段落点
- `[class*="item-user-info-nick"]` / `intro` — 卖家区（在 main 兄弟节点上）

每个节点记录：`classes`、`text`、直接子节点列表。  
再根据文案（如 `15.9 - 59.9`、`4750人想要`、`失眠小酥`）确认「这个节点就是价格/想要/卖家」。

启发式打分（class 关键词 + 文案正则）只用于**缩小候选**；最终选择器以结构 dump + 文案对齐为准。

### 4. CSS Modules：用 `[class*="语义片段"]`

真实 class：`price--OEWLbcxC`、`desc--GaIUKUQY`。  
哈希会变，固化时写成 `[class*="price"]`、`[class*="desc"]`，并加上 `[class*="item-main-info"]` 前缀，避免命中 feeds 里同名片段。

### 5. 写入 `extract.json`

`detail_dom` 全部进 JSON；`DETAIL_DOM_JS` 只读配置。翻版：重跑脚本看 `struct.json`，改 JSON 即可。

---

## 实测结构（过滑块后，来自 struct.json）

```text
item-container
├── item-user-container
│   ├── item-user-info-nick     → 卖家昵称（例：失眠小酥）
│   └── item-user-info-intro    → 「深圳 11分钟前来过 …」（地点取首段）
└── item-main-container
    ├── item-main-window        → 轮播图 img（carouselItem / fadeInImg）
    └── item-main-info
        ├── tips
        │   ├── value（活动价 / ¥ / price / 包邮）
        │   └── want（「4750人想要」+「6万浏览」两个子 div）
        ├── card                → 服务承诺文案
        └── notLoginContainer
            ├── main → desc    → 正文；标题=desc 下第一个有字 span
            ├── labels         → 「品牌：黑暗武士」
            └── buttons        → 聊一聊 / 立即购买 / 收藏
```

补充：

- 本页 `window.lib.mtop` 经常未就绪，仅靠 `VIEW_JS` 会失败，所以要 DOM 兜底。
- `notLoginContainer` 是正文外壳 class，不代表未登录。

---

## 固化到 `detail_dom` 的选择器

| 字段 | 选择器 / 规则 | 依据（结构分析） |
|------|----------------|------------------|
| 价格 | `[class*="item-main-info"] [class*="price"]` → 前缀 `¥` | `tips > value` 下 `price--*` 节点文案 |
| 想要 / 浏览 | `[class*="want"]` + `want_re` / `browse_re` | `want` 下两个子 div 文案 |
| 描述 | `[class*="desc"]` 全文 | `notLoginContainer > main > desc` |
| 标题 | `desc` 首个有字 `:scope > span` | `desc` 子 span 列表第一段 |
| 卖家 | `[class*="item-user-info-nick"]` | 用户区 nick 节点 |
| 地区 | `[class*="item-user-info-intro"]` 首段 | intro 文案拆分 |
| 主图 | `item-main-window` / `carouselItem` / `fadeInImg` 的 img | 左侧轮播树 |
| 品牌 | `[class*="labels"]` + `品牌：` | labels 节点文案 |

---

## 重跑探测

```bash
cd server
.venv\Scripts\python.exe scripts/probe_xianyu_detail_dom.py --item-id <id> --headless
.venv\Scripts\python.exe scripts/probe_xianyu_detail_struct.py
```

先看 `struct.json`（DOM 树），再对照截图与 `summary.json`；class 语义片段变了只改 `extract.json` 的 `detail_dom`。
