"""业务领域层包。

本包是 v2 后端的**核心业务所在**，所有 Agent、爬虫、调研、渠道、知识库等
逻辑都应实现在各子域的 ``service`` 模块中。

子域划分：
    agent     : AI 编排、LangGraph 工作流、工具调用
    crawler   : 爬虫任务与多平台 Provider
    research  : 市场调研与机会分析
    channel   : 渠道 WebSocket、消息桥接
    knowledge : 知识库索引与检索
    runtime   : 进程级运行时状态（非业务编排）

分层规则：
    - ``domains`` 不依赖 FastAPI，可被 CLI、测试直接调用
    - ``api`` 层通过调用本包服务对外暴露 HTTP
    - 访问数据库、事件总线时通过 ``infrastructure`` 层
"""
