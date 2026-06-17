"""limit_list_d 首次封板时间 map（re-export，实现见 integrations.tushare.limit_list_fallback）。"""

from vnpy_ashare.integrations.tushare.limit_list_fallback import load_limit_list_first_time_map

__all__ = ["load_limit_list_first_time_map"]
