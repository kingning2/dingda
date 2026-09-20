"""Agent 包：主编排 + 三个子 agent（爬虫 / 修复 / 验证）。

公开面只有下面几个模块，``import agent`` **不会**把它们带进来 —— 包初始化保持空的，
否则子模块（``agent.tools.*`` 要 import ``agent.loop``）会在这里撞成环。

    from agent.context import RunContext
    from agent.run import run_chat
    from agent.sse import EventBus

一次运行的形状：
    接线层注入 RunContext → run_chat 做登录门禁 → orchestrator 派活 →
    子 agent 执行 → 主编排判断够不够 → finish 收尾。
"""
