"""OpenAI Function Calling schema → LangChain StructuredTool。"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from langchain_core.tools import StructuredTool
from pydantic import Field, create_model

_JSON_TYPE_MAP: dict[str, type] = {
    "string": str,
    "integer": int,
    "number": float,
    "boolean": bool,
    "array": list,
    "object": dict,
}


def _args_model_from_schema(tool_name: str, schema: dict[str, Any]) -> type:
    props = schema.get("properties") or {}
    required = set(schema.get("required") or [])
    fields: dict[str, tuple[type, Any]] = {}
    for key, prop in props.items():
        json_type = prop.get("type", "string")
        py_type = _JSON_TYPE_MAP.get(json_type, str)
        desc = prop.get("description", "")
        if key in required:
            fields[key] = (py_type, Field(..., description=desc))
        else:
            fields[key] = (py_type | None, Field(default=None, description=desc))
    model_name = "".join(part.capitalize() for part in tool_name.split("_")) + "Args"
    if not fields:
        return create_model(model_name)
    return create_model(model_name, **fields)


def openai_tools_to_langchain(
    specs: list[dict[str, Any]],
    executor: Callable[[str, dict[str, Any]], str],
) -> list[StructuredTool]:
    """将 Skill OpenAI tools 转为 LangChain 可绑定工具。"""
    tools: list[StructuredTool] = []
    for spec in specs:
        fn = spec.get("function") or {}
        name = str(fn.get("name", "")).strip()
        if not name:
            continue
        parameters = fn.get("parameters") or {"type": "object", "properties": {}}
        args_model = _args_model_from_schema(name, parameters)

        def _make_run(tool_name: str) -> Callable[..., str]:
            def _run(**kwargs: Any) -> str:
                cleaned = {k: v for k, v in kwargs.items() if v is not None}
                return executor(tool_name, cleaned)

            return _run

        tools.append(
            StructuredTool(
                name=name,
                description=str(fn.get("description", "")),
                func=_make_run(name),
                args_schema=args_model,
            )
        )
    return tools
