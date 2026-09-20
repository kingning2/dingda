"""模型凭据与供应商目录契约。

职责：
    定义「模型配置」页与 HTTP 层之间的全部形状：供应商目录、凭据记录（含掩码 key）、
    新建 / 修改请求、可用模型列表、连通性检测结果、环境变量导入结果。

设计说明：
    - **``api_key`` 只进不出**：请求体里是原文，响应体里只有 ``api_key_masked``。
      改凭据时 ``api_key`` 传 ``None`` 或空串都表示「不改」，前端不回填原文
    - ``base_url`` 的「不改」与「清空」用 ``model_fields_set`` 区分：字段没出现 =
      不改，字段出现且为 ``None`` = 恢复供应商默认地址。不用 ``clear_base_url``
      这类额外开关，否则前端每加一个字段就要想一次该配哪个开关
    - 供应商 id **不写 Literal**：目录是数据驱动的（见 ``agent.llm.providers``），
      今天两个、明天可能三个，写死枚举等于把「新增供应商」变成跨包改动
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class LlmProviderView(BaseModel):
    """目录里的一行：某个 OpenAI 兼容供应商的静态事实。"""

    id: str
    name: str
    base_url: str
    default_model: str | None = None
    api_key_envs: list[str] = Field(default_factory=list)
    requires_model: bool = False
    """没有默认模型（豆包只认 ``ep-`` 接入点 ID）→ 前端必须要求用户手填。"""


class LlmProviderListResponse(BaseModel):
    ok: bool = True
    items: list[LlmProviderView]


class LlmCredentialRecord(BaseModel):
    """一条凭据的展示形状。``api_key`` 永不出现，只给掩码。"""

    credential_id: str
    provider: str
    provider_name: str
    label: str
    model: str
    base_url: str | None = None
    """用户自定义地址；``None`` 表示跟随供应商默认。"""

    effective_base_url: str
    """实际会用的地址（``base_url`` 为空时由供应商默认补上）。前端直接显示这个。"""

    api_key_masked: str
    has_api_key: bool = True
    is_active: bool = False
    last_check_at: float | None = None
    last_check_ok: bool | None = None
    last_check_message: str | None = None
    created_at: float
    updated_at: float


class LlmCredentialListResponse(BaseModel):
    ok: bool = True
    items: list[LlmCredentialRecord]
    active_id: str | None = None


class LlmCredentialCreateRequest(BaseModel):
    provider: str
    api_key: str
    model: str = ""
    label: str = ""
    base_url: str | None = None
    activate: bool = True
    """新建即生效（默认）。只在「我已经有一条在跑，先囤着备用」时才传 False。"""


class LlmCredentialUpdateRequest(BaseModel):
    """改凭据：字段缺省 = 不改。"""

    provider: str | None = None
    model: str | None = None
    api_key: str | None = None
    label: str | None = None
    base_url: str | None = None


class LlmCredentialResponse(BaseModel):
    ok: bool = True
    item: LlmCredentialRecord


class LlmCredentialDeleteResponse(BaseModel):
    ok: bool = True
    deleted: bool


class LlmModelListRequest(BaseModel):
    """按一组连接参数拉可用模型（凭据**还没保存**时用）。

    没有 ``model`` 字段：拉列表本就是为了知道该填什么模型。
    """

    provider: str
    api_key: str
    """key 原文；只在请求方向出现，不会回显。"""

    base_url: str | None = None
    """自定义地址；不传用供应商默认。"""


class LlmModelListResponse(BaseModel):
    """某个账号可用的模型列表。

    拉不到时**不报 HTTP 错**，而是 ``ok=False`` + ``message`` —— 与检测端点同一口径：
    「这把 key 拉不到列表」是业务结果，回 4xx 会让前端同时收到错误弹窗和一份结果。
    """

    ok: bool = True
    provider: str
    models: list[str] = Field(default_factory=list)
    default_model: str | None = None
    """目录里的默认模型；前端据此给对应卡片挂「默认」徽章。"""

    current_model: str | None = None
    """凭据当前填的模型；从表单拉取时为 ``None``。"""

    message: str | None = None
    """拉不到时的原因（含 ``llm.*`` 语义）；成功为 ``None``。"""


class LlmCheckView(BaseModel):
    """一次连通性检测的结果。``code`` 复用 ``agent`` 的 ``llm.*`` 错误码。"""

    ok: bool
    message: str
    code: str | None = None
    latency_ms: int | None = None
    reply: str | None = None
    model: str = ""
    provider: str = ""


class LlmCheckResponse(BaseModel):
    ok: bool = True
    check: LlmCheckView


class LlmImportEnvResponse(BaseModel):
    """把 ``.env`` / 真实环境里的那份配置收编成一条凭据。"""

    ok: bool = True
    imported: bool
    item: LlmCredentialRecord | None = None
    message: str = ""
