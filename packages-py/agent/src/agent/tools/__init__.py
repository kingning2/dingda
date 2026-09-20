"""工具层：agent 能对外做的每一个动作。

一个文件一类动作：

    login.py     扫码登录
    crawl.py     搜列表 / 拉详情
    repair.py    看 DOM、提候选选择器（不写盘）
    validate.py  试跑候选选择器、热更新
    risk.py      开有头窗口让人过风控

每个文件导出 ``TOOLS``（登记项），由 ``agent.loop.build_tools`` 绑成本次运行可用的
LangChain 工具。工具函数形状统一是 ``async fn(ctx, **kwargs) -> dict``，
失败用 ``ok=False`` + ``error_code`` 表达，不抛异常。
"""
