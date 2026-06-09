"""AI 内联工具 trace QSS。"""

INLINE_TRACE_STYLESHEET = """
QFrame#AiInlineTraceBlock {
    background-color: #17171e;
    border: 1px solid #2a2a34;
    border-radius: 8px;
}
QLabel#AiInlineTraceHeader {
    color: #a8a8b2;
    font-size: 11px;
}
QPushButton#AiInlineTraceStep {
    color: #c8c8d0;
    font-size: 11px;
    text-align: left;
    padding: 2px 4px;
    border: none;
}
QPushButton#AiInlineTraceStep:hover {
    color: #e8e8ec;
    background-color: #22222c;
    border-radius: 4px;
}
QPushButton#AiInlineTraceStep[stepStatus="running"] {
    color: #4a9eff;
}
QPushButton#AiInlineTraceStep[stepStatus="error"] {
    color: #ff8a8a;
}
QPlainTextEdit#AiInlineTraceDetail {
    background-color: #101016;
    border: 1px solid #2a2a32;
    border-radius: 4px;
    color: #b0b0b8;
    font-family: Menlo, Monaco, Consolas, monospace;
    font-size: 10px;
    padding: 6px;
}
"""
