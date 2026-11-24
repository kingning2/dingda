---
name: py-dev
description: 叮答 Python 端（packages-py/，uv workspace）编码规范。写或改 packages-py/ 下任何 Python 时使用：十个包各自收什么、目录树、代码示例形状、注意项与验证命令。禁止 Agent/Tool 直接 import Playwright、Camoufox、SQLite 或具体电商平台。
---

# Python 编码规范（packages-py）

## 0. 分层铁律（原文必遵，全局约束见根 AGENTS.md 第 2 节）

依赖方向唯一合法：`Agent → Tool → Crawler → BrowserPort → Adapter`。
八条核心规则全文在根 `AGENTS.md` 第 2.1 节，本文件不重复；跨层 import = 架构违规，直接打回。

## 1. 语言通用（写任何包之前）

1. **文件头**：模块 docstring 三段式——职责 / 设计说明 / 使用示例。范本：
   `packages-py/infrastructure/src/infrastructure/events/bus.py`。
2. **函数注释**：`def` 上方写「解决什么问题」，一行能说清就不写三行；不复述签名。
3. **日志**：`logging.getLogger("dingda.<pkg>.<module>")`；生命周期日志三段
   start → 关键步 → done|failed，字段用 `extra`；**禁止 print**、禁止 `getLogger(__name__)`。
4. **import**：跨包一律 `from src.<pkg>...`（照现有文件形状）；包内相对导入。
5. **错误**：业务错误只抛 `AppError(code, message, status_code=…)`
   （定义在 `packages-py/core/src/core/errors.py`），由 api 的全局异常处理器映射成 JSON；
   不在端点里手拼 4xx dict，不吞异常。
6. **少写边界分支**：输入在 api 层用 pydantic 校验后即视为合法；包内不再为空/类型/长度
   重复设防。
7. **命名**：文件/函数/变量 snake_case；类型 PascalCase；常量 UPPER_SNAKE；
   禁 `data2` / `result_final` / `temp`。
8. **一个功能块一个文件**：新目录先写 `README.md`（本仓 39 个目录 README 是惯例）。

✓ 示例（文件头 + 生命周期日志）：

```python
"""扫码登录渠道。

职责：
    生成登录二维码、轮询扫码状态、换取会话凭证。

设计说明：
    平台差异在 platform 名进入构造参数后消解，本类只认统一插座接口。

使用示例::
    channel = QrLoginChannel(platform="xianyu")
    await channel.start()
"""
import logging

log = logging.getLogger("dingda.channel.xianyu")

async def start(self) -> None:
    log.info("login.start", extra={"platform": self.platform})
    ...
    log.info("login.done", extra={"platform": self.platform})
```

✗ 反例：

```python
print("start login")            # 禁 print
def doIt(self): ...             # 禁小驼峰
if data is not None and len(data) > 0:  # api 已校验，包内不重复设防
```

## 2. 各包收什么（写错包 = 架构违规）

| 包 | 收什么 | 禁止 |
|----|--------|------|
| `agent/` | Planner / Executor / LangGraph / Workflow 编排 | import Playwright、Camoufox、SQLite、电商平台包 |
| `tools/` | Agent 可调用能力：名称 + 输入/输出 Schema + 错误模型 + timeout + cancellation | 隐式修改 Agent State |
| `crawler/` | 平台采集：搜索、详情、解析、标准化、Snapshot、Dedup | 平台特例进 core；直接依赖 Playwright/Camoufox |
| `browser/` | 启动、Context、Page、导航、点击、输入、Cookie、Session、截图、网络监听 | Xianyu/1688/商品/价格等业务词 |
| `channels/` | 登录/账号/IM 平台语义 | 碰浏览器（经 BrowserPort） |
| `api/` | HTTP 校验与调用，只做路由 | 写签名、开浏览器、碰 DB 逻辑 |
| `domains/` | 应用服务（按域分包） | `service.py` 上帝类 |
| `contracts/` | 与前端的线协议（pydantic） | 业务逻辑 |
| `infrastructure/` | db / events 底座 | 业务语义 |

## 2.1 插座模式（基类 + 多实现，跨包统一规则）

同一能力有多个平台/引擎实现时，**禁止在业务里写 if/else 选实现**，走六环。
范本 = 浏览器对接全链（文件全部实证，可直接照抄形状）：

| 环 | 落点 | 范本（实证） |
|----|------|------------|
| ① 插座 | 跨包消费 → `contracts/<域>_port.py`；包内消费 → `<pkg>/base.py` | `contracts/browser_port.py`：`BrowserPort(ABC)` + `Page(ABC)` 方法级抽象；参数对象用 frozen dataclass（`Cookie`/`LaunchOptions`，无平台特例） |
| ② 实现 | `adapters/<browser>/`、`sources/<platform>/`、`channels/<platform>/` | `browser/adapters/camoufox.py`：`class CamoufoxAdapter(BrowserPort)`，只填 launch/open/close 差异，共通逻辑留在 core/manager |
| ③ 注册表 | `<pkg>/registry.py`：`dict[名, type[插座]]` + `create_xxx(名)` 工厂 | `browser/registry.py` 原文「按 engine 名取出浏览器插头，避免业务里写 if」；未知名抛 `AppError` |
| ④ 生命周期收口 | manager/pool：acquire / release / stop，共享实例走 `get_xxx_manager()` | `browser/manager.py` 原文「Crawler 只拿返回的 BrowserPort，禁止自己 launch/close Camoufox」 |
| ⑤ 消费方注入 | 构造函数收**插座类型**，不 import 实现类 | `crawler/core/base.py`：`def __init__(self, browser: BrowserPort, ...)` |
| ⑥ 装配点 | 应用启动/停机建、停共享实例 | `api/boot/lifespan.py`：`get_browser_manager().stop()` |

✓ 新增一个实现（如新浏览器引擎）三步：写 `adapters/<name>.py` 实现插座全部抽象方法
→ registry 表加一行 → 完。**调用方零改动**。

✗ 禁止：

```python
# ① 调用方依赖具体实现（只准依赖插座类型；e2e 脚本除外，标注 noqa 即可）
from browser.adapters.camoufox import CamoufoxAdapter   # 业务代码里 = 违规
# ② 业务里选实现——选实现只允许发生在注册表
port = CamoufoxAdapter() if engine == "camoufox" else ...
# ③ 平台特例渗入插座/参数对象（Cookie 里出现闲鱼域名 = 违规）
```

同族插座范本：`channels/base.py` 的 `QrLoginChannel(ABC)`（ClassVar platform +
start_login/snapshot）、`crawler/core/base.py` 的 `BrowserCrawler`（同名抽象方法族）。
| `core/` | errors / http 机制底座 | 平台/业务语义 |

## 3. agent/

```
packages-py/agent/src/agent/
├── core/        # 状态、事件、公共类型
├── llm/         # 模型接入（DINGDA_LLM_* 环境变量决定，见 AGENTS.md 5.5）
├── subagents/   # 子 agent 编排
├── tools/       # 工具调用胶水（只经 Tool，不碰 Crawler 内部）
└── workflows/   # 业务流：research.py 等，一流程一文件
```

- 怎么写：一个 Workflow 一个文件；LangGraph 节点函数保持纯编排，脏活下放 Tool。
- ✓ 怎么用（实证 `workflows/research.py`）——日志命名到模块、入口由 api 调：

```python
class ResearchWorkflow:
    """调研业务流程入口（骨架）。

    经 Tool → Crawler 收集数据，不直接 import Playwright / Camoufox。
    由 ``api/research`` 调用本 Workflow。
    """

logger = logging.getLogger("dingda.agent.workflow.research")
```

- 注意：Agent 只会「决策 + 调 Tool」，出现 `import playwright` 即违规。

## 4. tools/

```
packages-py/tools/src/tools/
├── registry/    # 自动发现，无需手工注册
├── search/      # crawler.search_products
├── login/       # browser.open / snapshot.save
└── product/ compare/
```

- 怎么写：新 Tool 先 `uv run python -m tools.scaffold <name>` 生成骨架（AGENTS.md 4.2），
  一个 Tool 一个目录，`__init__.py` 内声明名称、输入/输出 Schema、错误模型、timeout。
- ✓ 怎么用（实证 `tools/compare/__init__.py`）——契约与执行同文件，四要素齐全：

```python
TOOL_NAME = "compare"
TOOL_DESCRIPTION = ("1688 同款比价：根据来源商品图片、链接或 source 元数据找同款，…")
DEFAULT_TIMEOUT_S = 90.0

class CompareInput(BaseModel):
    """比价入参。"""
    image: str | None = Field(default=None, description="来源商品图")
    # model_validator 校验「image / url / source 至少一个」

async def run_compare(inp: CompareInput) -> CompareOutput:  # 经 crawler/sources/ali1688，不经 Browser
    ...
```

- 注意：Tool 不隐式改 Agent State；产出统一走返回值；错误抛 `AppError`。

## 5. crawler/

```
packages-py/crawler/src/crawler/
├── core/        # CrawlTask、Dedup、Snapshot（平台无关）
├── extraction/  # 解析与标准化
└── sources/
    ├── xianyu/
    ├── ali1688/
    └── xiaohongshu/
```

- 怎么写（示例 A 形状——多平台插座基类）：平台差异实现 `sources/<platform>/`，
  统一插座在 core：

```python
class BrowserCrawler(ABC):
    """平台爬虫插座。

    职责：定义「给一个平台名，拿到标准化商品列表」的统一入口。
    子类只填平台差异；通用重试/限速/去重在 core 完成。
    """

    @abstractmethod
    async def search(self, keyword: str) -> list[ProductSnapshot]:
        """按关键字搜索并返回标准化快照。"""
```

- 注意：**平台新增只改 `sources/<platform>/`**；`core/` 里出现「闲鱼」「1688」字样即违规；
  Crawler 拿浏览器能力必须经 Browser Interface，禁直接 import Playwright/Camoufox。

## 6. browser/

```
packages-py/browser/src/browser/
├── core/              # 生命周期、Context、Page、Cookie、导航
└── adapters/
    └── camoufox.py    # 一个浏览器一个适配器文件
```

- 怎么写：通用能力进 core；具体浏览器差异进 `adapters/<browser>/`（新增浏览器只改这里）。
- ✓ 怎么用（实证 `adapters/camoufox.py`）——适配器 = 实现 `BrowserPort` 协议插座的插件：

```python
"""Camoufox 插头：通用 launch / context / page，无平台业务。"""

from contracts.browser_port import BrowserPort, Cookie, LaunchOptions, Page

class CamoufoxAdapter(BrowserPort):
    # 只提供通用能力；启动环境变量（DINGDA_CAMOUFOX_EXE）由壳注入
    ...
```

- 注意：本包出现「商品 / 价格 / 搜索结果」等业务词即违规；只提供 Session/Cookie/导航等
  通用能力，登录语义归 channels。

## 7. channels/

```
packages-py/channels/src/channels/
├── base.py            # 插座定义
├── ali1688/
├── xianyu/
└── xiaohongshu/
```

- 怎么写（示例 B 形状——多实现插座）：新增登录渠道只改 `channels/<platform>/`：

```python
class QrLoginChannel:
    """扫码登录渠道（示例形状，范本见 xianyu/）。

    职责：qr/start → qr/check → 换取会话凭证，语义归平台。
    """

    def __init__(self, platform: str) -> None:
        self.platform = platform
```

- 注意：登录凭证、账号语义、IM 都在这里；不要把「打开浏览器」写进来（经 BrowserPort）。

## 8. api/

```
packages-py/api/src/api/
├── boot/            # 应用装配、lifespan、异常处理器注册
├── lib/             # 响应包裹、分页等公共件
└── routes/
    ├── bootstrap.py health.py
    ├── account/     # list_accounts.py patch_account.py ...
    ├── channel/     # qr_start.py qr_check.py qr_cancel.py
    └── agent/       # list_works.py run_work.py ...
```

- **一端点一文件**：文件名 = 动作；一个路由文件只注册一个 HTTP 方法与路径，
  读取/保存拆开（AGENTS.md 4.1）。域 `__init__.py` 挂 `APIRouter(prefix, tags)`，
  在 `routes/__init__.py` 聚合。

路由映射（实证形状）：

| 文件 | 方法 | 路径 |
|------|------|------|
| `routes/channel/qr_start.py` | POST | `/v1/channel/qr/start` |
| `routes/channel/qr_check.py` | GET | `/v1/channel/qr/check` |
| `routes/account/list_accounts.py` | GET | `/v1/accounts` |
| `routes/account/patch_account.py` | PATCH | `/v1/accounts/{account_id}` |
| `routes/agent/run_work.py` | POST | `/v1/agent/works/{work_id}/run` |

端点骨架：

```python
@router.post("/qr/start", response_model=QrStartResponse)
async def qr_start(req: QrStartRequest) -> QrStartResponse:
    """发起扫码登录。只做：校验（pydantic 已做）→ 调 domain → 返回契约模型。"""
    return await channel_service.start_qr(req)
```

- 注意：请求 DTO 放本域 `_dto.py`；`response_model` 一律用 contracts 的 `*Response`；
  业务错误抛 `AppError`，端点里不写 try/except 拼错误 JSON；
  **测试统一放 `packages-py/api/tests/<域>/`，不跟包走**。

## 9. domains/

```
packages-py/domains/src/domains/
├── account/  channel/  knowledge/
└── runtime/  watch/                   # watch: base/insight/poller/scheduler/service
```

- 怎么写：应用服务按域分包；`service.py` 只做该域编排，超过一个职责就拆文件。
- ✓ 怎么用（实证 `domains/watch/service.py`）——组装视图 + 展示口径在这算完：

```python
"""监控目标的增删改查与视图组装。

设计说明：
    - 价格涨跌这类展示口径（比首价降了多少、是否处在最低点）在这里算完，
      API 层只做序列化，不重复推导
    - 不轮询、不发请求；取数在 ``poller``，排期在 ``scheduler"
"""

from contracts.watch import SoldState, WatchState
from infrastructure.db import watch as watch_repo
```

- 注意：禁上帝类；新代码目录优先放 `packages-py/{agent,crawler,browser,tools}/src/<pkg>/`
  （AGENTS.md 5.4），domains 只放跨包应用服务；service 只编排，不直接发请求。

## 10. contracts / infrastructure / core

### contracts（`src/contracts/`，按域一文件：account/agent/channel/crawler/watch/…）

- 怎么写：pydantic 模型即线协议；改字段**先改这里再改实现**（AGENTS.md 4.6），
  并与 `packages/contracts` 同步；响应模型命名 `*Response`。
- ✓ 怎么用（实证 `contracts/account.py`）：

```python
AccountPlatform = Literal["xianyu", "ali1688", "xiaohongshu"]

class AccountRecord(BaseModel):
    account_id: str
    platform: AccountPlatform
    display_name: str
    avatar_url: str | None = None
    cookie: str
```

- 注意：不写逻辑、不发请求；`browser_port.py` 这类插座协议也归这里。

### infrastructure（`db/` + `events/bus.py`）

- 怎么写：SQLite 只在这一层（其他包禁直接碰 sqlite3）；事件总线 topic 与契约事件名对齐。
- ✓ 怎么用（实证 `events/bus.py` 文件头）：

```python
bus = EventBus()
bus.subscribe(forward_to_websocket)          # 订阅方在应用启动时注册
bus.publish("agent/run/started", {"task_id": "..."})   # 推给 SSE/日志/指标
```

- 注意：当前是单进程内存实现，不跨进程不持久化；别在这里写业务语义。

### core（`errors.py` + `logging.py` + `config.py` + `http/transports/`）

- 怎么写：机制底座；`AppError` 唯一定义处（抛法见第 1 节第 5 条）。
- 注意：不出现平台/业务语义；HTTP 传输实现收在 `http/transports/`。

## 11. 验证要求（交码前必跑）

```bash
uv run ruff check packages-py --select E4,E7,E9,F
uv run pytest packages-py/api/tests -m "not integration"   # 集成测试只在本地跑
```

- 改了 `routes/`：`uv run python -m api` 起本地服务实际打一发请求再交。
- 改了 `contracts/`：确认 `packages/contracts`（TS 侧）已同步。
