"""个股股东结构。

实现已迁至 ``services.stock.holders``；本模块保留 re-export。
"""

from vnpy_ashare.services.stock.holders import HolderProfile, build_holder_profile

__all__ = ["HolderProfile", "build_holder_profile"]
