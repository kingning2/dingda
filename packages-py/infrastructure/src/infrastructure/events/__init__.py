"""事件基础设施包导出。

导出进程内 ``EventBus``，用于领域层发布事件。
"""

from infrastructure.events.bus import EventBus

__all__ = ["EventBus"]
