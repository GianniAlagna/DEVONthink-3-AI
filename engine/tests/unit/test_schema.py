import pytest

from dt3agent.schema import SchemaError, check

SCHEMA = {
    "type": "object",
    "properties": {
        "language": {"type": "string", "enum": ["de", "fr", "it", "en"]},
        "amount": {"type": ["number", "null"]},
        "tags": {"type": "array", "items": {"type": "string", "maxLength": 20}, "maxItems": 3},
        "summary": {"type": "array", "items": {"type": "string"}, "minItems": 1},
    },
    "required": ["language", "amount", "tags"],
    "additionalProperties": False,
}
GOOD = {"language": "de", "amount": 12.5, "tags": ["invoice"]}


def test_valid_object_passes():
    check(GOOD, SCHEMA)
    check(dict(GOOD, amount=None, summary=["a"]), SCHEMA)


@pytest.mark.parametrize("bad, where", [
    ("not a dict", "$"),
    ({"amount": 1, "tags": []}, "$.language"),
    (dict(GOOD, language="es"), "$.language"),
    (dict(GOOD, amount="12"), "$.amount"),
    (dict(GOOD, amount=True), "$.amount"),  # bool is not a number
    (dict(GOOD, tags=["a", "b", "c", "d"]), "$.tags"),
    (dict(GOOD, tags=["x" * 21]), "$.tags[0]"),
    (dict(GOOD, tags=[1]), "$.tags[0]"),
    (dict(GOOD, summary=[]), "$.summary"),
    (dict(GOOD, extra=1), "$.extra"),
])
def test_invalid_objects_name_the_path(bad, where):
    with pytest.raises(SchemaError) as e:
        check(bad, SCHEMA)
    assert e.value.path == where


def test_unsupported_keyword_is_refused_not_ignored():
    with pytest.raises(ValueError):
        check("x", {"type": "string", "pattern": "^x$"})
