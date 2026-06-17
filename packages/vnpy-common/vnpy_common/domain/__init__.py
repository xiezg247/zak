"""跨包共享的领域模型基类。"""

from vnpy_common.domain.base import FrozenModel, MutableModel
from vnpy_common.domain.serialize import dump_json, dump_python

__all__ = ["FrozenModel", "MutableModel", "dump_json", "dump_python"]
