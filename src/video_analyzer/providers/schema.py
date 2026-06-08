"""Convert Pydantic JSON schemas to OpenAI/OpenRouter strict-mode schemas.

strict:true requires every object to set additionalProperties:false and list
all of its properties in `required`. Pydantic's model_json_schema() does neither.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel


def _strictify(node: Any) -> None:
    if isinstance(node, dict):
        if node.get("type") == "object" or "properties" in node:
            props = node.get("properties", {})
            node["additionalProperties"] = False
            node["required"] = list(props.keys())
            for sub in props.values():
                _strictify(sub)
        if isinstance(node.get("items"), dict):
            _strictify(node["items"])
        for combinator in ("anyOf", "oneOf", "allOf"):
            for sub in node.get(combinator, []):
                _strictify(sub)
    elif isinstance(node, list):
        for sub in node:
            _strictify(sub)


def pydantic_to_strict_schema(model: type[BaseModel]) -> dict:
    schema = model.model_json_schema()
    _strictify(schema)
    for definition in schema.get("$defs", {}).values():
        _strictify(definition)
    return schema
