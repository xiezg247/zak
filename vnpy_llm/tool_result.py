"""工具调用结果规范化：错误提示增强。"""

from __future__ import annotations

import json
import re
from typing import Any

_ERROR_HINTS: tuple[tuple[str, str], ...] = (
    (r"无法解析代码", "请使用 vt_symbol 格式，例如 600519.SSE、000001.SZSE"),
    (r"K 线数量不足|暂无足够 K 线", "请先在「自选/市场/本地」页选中该标的并下载日K到本地"),
    (r"本地日 K：暂无|暂无（需先下载）", "请先在「自选/市场/本地」页点击「下载日K到本地」"),
    (r"MCP Provider 未连接|MCP 未连接", "请检查 mcp/mcp.json 中的 API Key 配置并重启终端"),
    (r"未注册的 MCP 工具|未注册的工具|未知工具", "该工具当前不可用，请换用其他工具或检查 Skills/MCP 配置"),
    (r"Service 未就绪", "A 股引擎未完全加载，请重启终端或确认 vnpy_ashare 插件已启用"),
    (r"选股方案不存在", "请调用 list_screeners 查看可用 preset 或 scheme_id"),
    (r"超时|timeout", "数据源响应较慢，请稍后重试或缩小查询范围"),
)


def match_error_hint(error: str) -> str:
    """根据错误文案匹配操作建议。"""
    text = error.strip()
    if not text:
        return ""
    for pattern, hint in _ERROR_HINTS:
        if re.search(pattern, text, flags=re.IGNORECASE):
            return hint
    return ""


def enrich_tool_result(result: str) -> str:
    """为 JSON 工具结果中的 error 附加 hint / message，便于 LLM 与用户理解。"""
    text = (result or "").strip()
    if not text:
        return result
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return result
    if not isinstance(payload, dict):
        return result
    error = payload.get("error")
    if error is None:
        return result
    error_str = str(error).strip()
    if not error_str:
        return result
    hint = str(payload.get("hint") or "").strip() or match_error_hint(error_str)
    if not hint:
        return result
    enriched: dict[str, Any] = dict(payload)
    enriched["hint"] = hint
    if not str(payload.get("message") or "").strip():
        enriched["message"] = f"{error_str}。{hint}"
    return json.dumps(enriched, ensure_ascii=False)
