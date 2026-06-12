"""通达信问小达（tdx_wenda_quotes）个股综合诊断。

实现已迁至 ``services.analysis.tdx_diagnose``；本模块保留 re-export。
"""

from vnpy_ashare.services.analysis.tdx_diagnose import (
    run_tdx_diagnose,
    _call_wenda,
    _parse_wenda_table,
    _pick_wenda_tool,
    _to_float,
)

__all__ = [
    "run_tdx_diagnose",
    "_call_wenda",
    "_parse_wenda_table",
    "_pick_wenda_tool",
    "_to_float",
]
