"""个股概念/题材。

实现已迁至 ``services.stock.concept``；本模块保留 re-export。
"""

from vnpy_ashare.services.stock.concept import ConceptProfile, build_concept_profile

__all__ = ["ConceptProfile", "build_concept_profile"]
