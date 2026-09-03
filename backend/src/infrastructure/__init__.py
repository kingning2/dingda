"""基础设施层包。

本包封装与具体业务无关的技术实现，供 ``domains`` 层调用：

子模块：
    db/      本地 SQLite 连接、迁移、Repository 基座
    events/  进程内事件总线，用于领域事件 -> WebSocket/SSE 推送

分层规则：
    - ``domains`` 通过本包访问外部世界（数据库、消息、第三方 API 适配器）
    - ``api`` 层一般不直接 import 本包，经 domain service 间接使用
    - 未来可扩展：cache/、http_client/、vector_store/ 等
"""
