"""第三方适配层包。

职责：
    为 ``third_party/`` 下的 vendored 工具提供**稳定、版本无关**的 Python API。
    业务域（``domains``）只能 import 本包，不得直接 import 第三方目录。

子模块：
    bootstrap  : 启动时将 vendor 的 ``python_path`` 加入 ``sys.path``
    registry   : 按 ``manifest.yaml`` 动态加载 vendor 模块
    crawler    : 爬虫相关第三方（小红书、闲鱼等）的稳定封装

设计目标：
    升级 ``third_party/xhs_cli`` 等目录时，只要上游公开 API 兼容，
    无需修改 ``domains`` / ``api`` 中的业务代码。
"""
