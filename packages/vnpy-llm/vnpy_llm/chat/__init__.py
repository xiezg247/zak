"""对话客户端、会话存储与多 Surface 绑定。"""

from vnpy_llm.chat.client import LlmClientError, StreamCancelled, complete_chat_completion, stream_chat_completion
from vnpy_llm.chat.session_surface import SessionSurfaceStore, Surface
from vnpy_llm.chat.store import MAX_TOOL_RESULT_CHARS, ChatMessage, ChatSession, ChatStore

__all__ = [
    "ChatMessage",
    "ChatSession",
    "ChatStore",
    "LlmClientError",
    "MAX_TOOL_RESULT_CHARS",
    "SessionSurfaceStore",
    "StreamCancelled",
    "Surface",
    "complete_chat_completion",
    "stream_chat_completion",
]
