"""B-4 retention classes (brief B4): a user-editable table, shown as a hint, never legal advice, never deletes."""
import copy
from datetime import date

import pytest

from dt3agent import config
from dt3agent.retention import NOTE, keep_until


def test_period_runs_from_the_end_of_the_year():
    # OR Art. 958f: 10 years from the end of the business year (calendar year assumed)
    assert keep_until(date(2026, 4, 17), 10) == date(2036, 12, 31)
    assert keep_until(date(2026, 12, 31), 10) == date(2036, 12, 31)
    assert keep_until(date(2026, 1, 1), 0) == date(2026, 12, 31)


def test_default_table_is_an_example_with_its_source():
    classes = config.DEFAULTS["retention"]["classes"]
    assert classes["invoice"] == {"years": 10, "basis": "OR Art. 958f"}
    assert "Keine Rechtsberatung" in NOTE


@pytest.mark.parametrize("classes", [
    {"invoice": {"years": -1, "basis": "x"}},
    {"invoice": {"years": 101, "basis": "x"}},
    {"invoice": {"years": True, "basis": "x"}},
    {"invoice": {"years": 10}},
    {"invoice": {"years": 10, "basis": "x", "delete": True}},
    {"": {"years": 10, "basis": "x"}},
])
def test_bad_tables_are_refused(classes):
    c = copy.deepcopy(config.DEFAULTS)
    c["retention"]["classes"] = classes
    with pytest.raises(config.ConfigError):
        config.validate(c)


def plan_for(text_change=None, **retention):
    from dt3agent.plan import plan
    from tests.unit.test_plan import AI, TEXT, by_field, cfg
    c = cfg()
    c["retention"] = {**c["retention"], **retention}
    text = TEXT if text_change is None else text_change(TEXT)
    return by_field(plan({}, text, AI, c))


def test_invoice_gets_keep_until_and_basis():
    p = plan_for()
    assert p[("metadata", "dt3agentretention")].value == "2036-12-31"
    assert p[("metadata", "dt3agentretentionbasis")].value == f"OR Art. 958f · {NOTE}"
    # as sure as the weakest input: the rule type (0.8) keeps it in review until the user trusts it
    assert p[("metadata", "dt3agentretention")].confidence == 0.8


def test_off_or_unknown_type_gives_nothing():
    assert ("metadata", "dt3agentretention") not in plan_for(enabled=False)
    assert ("metadata", "dt3agentretention") not in plan_for(classes={"contract": {"years": 10, "basis": "x"}})
