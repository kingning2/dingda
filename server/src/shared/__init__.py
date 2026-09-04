"""跨层共享工具包。

存放不归属于单一领域、但被多层复用的代码：
    - 统一业务异常（``errors``）
    - 通用工具函数（未来可增 ``utils`` 子模块）

原则：
    避免把业务逻辑放进 shared；仅放真正横切的、无领域语义的工具。
"""

from src.shared.errors import AppError

__all__ = ["AppError"]
