from video_analyzer.providers.schema import pydantic_to_strict_schema
from video_analyzer.models import SizzleResult


def _walk_objects(node):
    """Yield every object-typed subschema (including under $defs)."""
    if isinstance(node, dict):
        if node.get("type") == "object" or "properties" in node:
            yield node
        for v in node.values():
            yield from _walk_objects(v)
    elif isinstance(node, list):
        for v in node:
            yield from _walk_objects(v)


def test_every_object_is_strict():
    schema = pydantic_to_strict_schema(SizzleResult)
    objs = list(_walk_objects(schema))
    assert objs, "expected at least one object schema"
    for obj in objs:
        assert obj.get("additionalProperties") is False
        assert set(obj["required"]) == set(obj.get("properties", {}).keys())


def test_defs_are_strictified():
    schema = pydantic_to_strict_schema(SizzleResult)
    # SizzleResult nests per-moment objects in $defs
    assert "$defs" in schema
    for d in schema["$defs"].values():
        if d.get("type") == "object":
            assert d["additionalProperties"] is False
