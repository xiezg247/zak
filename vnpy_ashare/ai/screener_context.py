"""选股页 AI 上下文。"""

from __future__ import annotations

from vnpy_ashare.ai.context import AiContextData
from vnpy_ashare.ai.session_context import get_screening_results, set_ai_context


def sync_screener_page_context(main_engine=None) -> None:
    ctx = get_screening_results()
    if ctx is None or ctx.count == 0:
        extra = "当前无选股结果。请用户先在选股页运行方案，或询问如何设置筛选条件。"
        data = AiContextData(page="选股", extra=extra)
    else:
        preview = ctx.rows[:5]
        lines = [
            "你正在协助用户解读选股结果；数值来自规则引擎，禁止编造。",
            f"最近选股：「{ctx.condition}」命中 {ctx.count} 条",
        ]
        if ctx.updated_at:
            lines.append(f"更新时间：{ctx.updated_at}")
        lines.append("Top 预览：")
        for index, row in enumerate(preview, start=1):
            symbol = row.get("vt_symbol") or row.get("symbol", "")
            name = row.get("name", "")
            change = row.get("change_pct", "")
            lines.append(f"  {index}. {symbol} {name} {change}")
        if ctx.count > len(preview):
            lines.append(f"  … 另有 {ctx.count - len(preview)} 条，可调用 get_screening_context 查看")
        data = AiContextData(page="选股", extra="\n".join(lines))

    set_ai_context(data)
    if main_engine is None:
        return
    try:
        from vnpy_llm.engine import APP_NAME, LlmEngine

        engine = main_engine.get_engine(APP_NAME)
        if isinstance(engine, LlmEngine):
            engine.signals.context_changed.emit(data.to_text())
    except Exception:
        pass


def build_ask_ai_prompt_for_run(run_id: str, condition: str) -> str:
    """生成「发给 AI 解读历史选股」的预填文案。"""
    condition = condition.strip() or "（未知条件）"
    return (
        f"请解读这次选股历史（条件：{condition}）。"
        f'请调用 get_screening_context(run_id="{run_id}", batch_top_n=5) '
        "获取结果并解读前几只标的，不要编造未在结果中的指标。"
    )
