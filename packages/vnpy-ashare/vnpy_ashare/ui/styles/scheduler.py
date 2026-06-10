"""QSS：SCHEDULER。"""

from vnpy_common.ui.theme.build_extra import (
    build_scheduler_page_stylesheet,
    build_scheduler_table_stylesheet,
)
from vnpy_common.ui.theme.tokens import DARK_TOKENS

SCHEDULER_TABLE_STYLESHEET = build_scheduler_table_stylesheet(DARK_TOKENS)
SCHEDULER_PAGE_STYLESHEET = build_scheduler_page_stylesheet(DARK_TOKENS)
