"""爬虫第三方适配包。

对外暴露稳定函数，内部通过 ``registry`` 加载 ``third_party`` 中的实现。
``domains.crawler`` 只应 import 本包。
"""

from src.adapters.crawler.goofish import get_goofish_session_factory
from src.adapters.crawler.xhs import get_xhs_client_class

__all__ = ["get_xhs_client_class", "get_goofish_session_factory"]
