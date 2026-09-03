"""第三方工具根目录（非业务代码）。

本目录存放从上游 vendored 的第三方 Python 包，可**整目录覆盖更新**，
业务代码不得直接 ``import`` 本目录下的模块。

使用方式：
    1. 业务只通过 ``src.adapters`` 访问第三方能力
    2. 升级时运行 ``tooling/sync_vendor.py --update <name>``；按锁同步见 ``vendor.lock.yaml``
    3. 登记信息见 ``manifest.yaml``，锁定版本见 ``vendor.lock.yaml``

注意：
    此目录不参与 ruff/类型检查约束；许可证文件（LICENSE/NOTICE）须随包保留。
"""
