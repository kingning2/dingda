"""API 契约模型包。

本包定义 HTTP 请求/响应的 Pydantic 模型，作为前后端与测试的数据契约。

来源与演进：
    - 当前为手写骨架，字段与旧版 sidecar 及 ``contracts/schema`` 逐步对齐
    - 后续可通过 codegen 从 ``contracts/schema/v1/*`` 自动生成，减少漂移

子模块：
    agent.py    Agent 相关 DTO
    crawler.py  爬虫任务 DTO
    research.py 调研任务 DTO

使用约定：
    - ``api`` 路由用这些模型做入参/出参校验
    - ``domains`` 层可使用相同模型，或转换为内部领域对象
"""
