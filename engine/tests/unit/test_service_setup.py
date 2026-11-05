"""Rpc helpers for onboarding (U-2): naming preview and the open DT3 databases."""
import pytest

from dt3agent.rpc import RPCError
from tests.unit.test_service import env  # noqa: F401  (fixture)


def test_naming_preview_uses_a_fixed_sample(env):  # noqa: F811
    svc, _, _ = env
    out = svc.handle("naming_preview", {"template": "{date}_{sender}_{subject}"})
    assert out == {"name": "20261217_Muster-Treuhand-AG_Rechnung-2026-0417"}


def test_naming_preview_default_template(env):  # noqa: F811
    svc, _, _ = env
    name = svc.handle("naming_preview", {"template": "{datetime}_{sender}_{receiver}_{subject}"})["name"]
    assert name == "20261217000000_Muster-Treuhand-AG_Erika-Beispiel_Rechnung-2026-0417"


@pytest.mark.parametrize("template", ["", "no tokens", "{nope}", "{date}_{bad}", 5, "x" * 201])
def test_naming_preview_refuses_bad_templates(env, template):  # noqa: F811
    svc, _, _ = env
    with pytest.raises(RPCError) as e:
        svc.handle("naming_preview", {"template": template})
    assert str(e.value) == "naming_invalid"


def test_config_refuses_a_template_with_unknown_tokens(env):  # noqa: F811
    svc, _, _ = env
    with pytest.raises(RPCError) as e:
        svc.handle("config_set", {"changes": {"naming": {"template": "{date}_{nope}"}}})
    assert str(e.value) == "config_invalid"


def test_dt3_info_lists_open_databases(env):  # noqa: F811
    svc, _, _ = env
    out = svc.handle("dt3_info", {})
    assert out["version"] == "3.9.17" and isinstance(out["databases"], list)


def test_dt3_info_when_dt3_does_not_answer(env):  # noqa: F811
    svc, dt3, _ = env
    dt3.fail_info = True
    with pytest.raises(RPCError) as e:
        svc.handle("dt3_info", {})
    assert str(e.value) == "dt3_unreachable"
