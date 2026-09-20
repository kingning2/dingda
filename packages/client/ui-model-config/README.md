# ui-model-config

模型配置域：管理「用哪个供应商、哪把 key、哪个模型」——**多条并存，一条生效**。

一个桌面产品里可能有：同一个供应商的两把 key（主号 / 备用）、不同供应商各一把
（DeepSeek 跑日常、豆包跑便宜量大的活）。所以这一页的模型是**列表**，不是一张表单。

不负责「怎么跟模型说话」（那是
[agent/llm](../../../packages-py/agent/src/agent/llm/README.md)），
不负责 key 的落盘（那是
[domains/llm](../../../packages-py/domains/src/domains/llm/README.md) +
`infrastructure/db/llm_credentials.py`）。

## 本目录文件

### `model-config-hub.tsx`

页面级装配：拉目录与列表、渲染加载 / 空态 / 列表 / 错误，串起卡片动作与表单弹窗。

两条纪律：

- **不建全局 store**：这一页的数据是单页的，`useState` + `useCallback` 的 `refresh`
  就够（与 [ui-monitor](../ui-monitor/README.md) 同一个判断）
- **不做 mock 兜底**：账号页在浏览器里会展示演示账号，但这一页展示的是凭据 ——
  编造出来的 key 与「使用中」标记会让人以为真配好了。服务未就绪就明说

### `model-credential-card.tsx`

单条凭据卡片 + 删除二次确认。四个动作：测试连接 / 设为使用中 / 编辑 / 删除。

检测结果由上层传进来（`check`），卡片只负责显示 —— 那是「刚点过的那一次」，
不是凭据的持久属性；持久那份是后端的 `last_check_*`。

### `model-credential-form.tsx`

新增 / 编辑共用弹窗。差异只有标题文案与「key 留空 = 不改」这一条。

**编辑时不回填 key 原文**（后端只回掩码，前端也拿不到），所以输入框占位符必须写清
「留空表示不修改」，否则用户会以为 key 丢了。

**拉模型的时机是显式的**，不是 `useEffect` 盯着 `values` —— 那样每敲一个字符 key 就发
一次请求。触发点只有五个：打开弹窗、换供应商、key 失焦、地址失焦、点「重新获取」。

### `model-field.tsx`

表单里的「模型」字段：卡片网格供点选，拉不到时退回手填输入框，下方永远有一行状态说明。

两条纪律：

- **永远留着手填出口**：`/models` 只回上游肯给的模型 —— 方舟只认推理接入点 ID
  （列表里根本没有）、有的中转只列一部分。只给卡片等于把这类账号锁死
- 状态行**永远有字**：空着看起来像加载失败。四种状态的文案统一由 `modelListHint` 给，
  组件里不做 `if` 拼字符串

### `model-picker.tsx`

模型卡片网格。卡片主行是**模型 id 本身**（等宽字体）—— 用户要拿它去供应商控制台里
对上号，人话标签只是辅助。选中态靠边框 + 勾选图标 + 徽章三重表达，不只换背景色。

### `use-model-list.ts`

模型列表的获取状态机：按「供应商 + key + 地址」拉一次，收成 `ModelListPhase`。

- **触发点显式**（`load(values)`），不写成依赖 `values` 的 effect
- **用序号而不是 `AbortController` 防竞态**：请求已经发出去了，取消只省一次解析；
  真正要防的是「先发的后到」把新列表覆盖成旧的
- 拉不到**不是异常**：`ok=false` 收成 `failed` 状态，文案直接用后端那句

### `model-credential-view.ts`

纯函数：标题、副标题、最近检测状态、表单初值、请求体拼装、表单校验、模型卡片数据。
不依赖 React / DOM。

两处是各自纪律的**唯一落点**，所以必须可单测，不能散在组件里：

- `buildUpdateBody` —— **「只放要改的字段」**。后端按「字段在不在请求体里」判断改不改
- `modelFetchPlan` —— **「这次该用哪把 key 拉模型」**。编辑态换了供应商时必须改用新 key，
  否则会拿旧供应商的 key 去新家拉，报出来的却是「API key 无效」

### `model-config-api.ts`

`/v1/llm` 的类型化包装。统一 `skipErrorToast: true`：探活失败与拉模型列表失败本身都是
**200 + `ok=false`**，不是异常，提示交给调用方。

### `index.ts`

包入口，只暴露 `ModelConfigHub`。

## 子目录

- [tests/](tests/README.md) — 纯函数测试
