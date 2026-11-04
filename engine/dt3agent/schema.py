"""Small JSON-Schema subset check for AI output (SPEC §4.9: output is untrusted).

Supported keywords: type (incl. lists and "null"), enum, properties, required, additionalProperties (false only),
items, minItems, maxItems, maxLength. Any other keyword raises ValueError, so a schema is never half-checked.
"""
SUPPORTED = {"type", "enum", "properties", "required", "additionalProperties", "items", "minItems", "maxItems",
             "maxLength", "name", "description"}


class SchemaError(ValueError):
    def __init__(self, path: str, reason: str):
        super().__init__(f"{path}: {reason}")
        self.path, self.reason = path, reason


def _is_type(value, t: str) -> bool:
    if t == "null":
        return value is None
    if t == "boolean":
        return isinstance(value, bool)
    if t == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if t == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if t == "string":
        return isinstance(value, str)
    if t == "array":
        return isinstance(value, list)
    if t == "object":
        return isinstance(value, dict)
    raise ValueError(f"unsupported type {t!r}")


def check(value, schema: dict, path: str = "$") -> None:
    unknown = set(schema) - SUPPORTED
    if unknown:
        raise ValueError(f"unsupported schema keywords: {sorted(unknown)}")
    if "type" in schema:
        types = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
        if not any(_is_type(value, t) for t in types):
            raise SchemaError(path, f"expected {'/'.join(types)}")
    if "enum" in schema and value not in schema["enum"]:
        raise SchemaError(path, "not an allowed value")
    if isinstance(value, str) and len(value) > schema.get("maxLength", len(value)):
        raise SchemaError(path, "too long")
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0) or len(value) > schema.get("maxItems", len(value)):
            raise SchemaError(path, "wrong number of items")
        if "items" in schema:
            for i, item in enumerate(value):
                check(item, schema["items"], f"{path}[{i}]")
    if isinstance(value, dict):
        props = schema.get("properties", {})
        for key in schema.get("required", []):
            if key not in value:
                raise SchemaError(f"{path}.{key}", "missing")
        if schema.get("additionalProperties", True) is not True:
            if schema["additionalProperties"] is not False:
                raise ValueError("additionalProperties: only true/false supported")
            for key in value:
                if key not in props:
                    raise SchemaError(f"{path}.{key}", "not allowed")
        for key, sub in props.items():
            if key in value:
                check(value[key], sub, f"{path}.{key}")
