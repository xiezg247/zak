"""注册 vnpy_common 与 vnpy_ashare 之间的桥接（路径、AI 上下文、主题图表）。"""

from __future__ import annotations

import vnpy_ashare.ai.context.store as context_store
import vnpy_common.ai.access as access
from vnpy_ashare.ai.context.market_overview import build_market_ai_prompt
from vnpy_ashare.ai.context.quote.assembly import build_stock_completion_items
from vnpy_ashare.ai.ui.floating_actions import build_quick_actions_for_panel
from vnpy_ashare.ai.ui.symbol_navigation import build_ashare_symbol_navigation
from vnpy_ashare.config.vt_settings import load_runtime_settings
from vnpy_ashare.services.analysis_detail.team_report import (
    persist_team_analysis_report,
    team_report_href,
)
from vnpy_ashare.ui.components.chart_style import refresh_charts_for_theme
from vnpy_common.ai.symbol_navigation import register_symbol_navigation
from vnpy_common.paths import register_settings_loader
from vnpy_common.ui.theme.manager import theme_manager


def install_shared_bridges() -> None:

    register_settings_loader(load_runtime_settings)
    access.register_context_store(
        get_ai_context=context_store.get_ai_context,
        register_context_listener=context_store.register_context_listener,
    )
    access.register_screening_accessor(context_store.get_screening_results)
    access.register_stock_completion_builder(build_stock_completion_items)
    access.register_panel_actions_builder(build_quick_actions_for_panel)
    access.register_market_prompt_builder(build_market_ai_prompt)
    access.register_team_report_bridge(
        persist_team_analysis_report=persist_team_analysis_report,
        team_report_href=team_report_href,
    )
    register_symbol_navigation(build_ashare_symbol_navigation())
    theme_manager().register_chart_refresh_handler(refresh_charts_for_theme)
