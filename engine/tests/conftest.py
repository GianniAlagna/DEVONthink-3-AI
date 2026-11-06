"""Shared test setup."""
import pytest


@pytest.fixture(autouse=True)
def _no_host_power_readings(monkeypatch, request):
    """Service tests must not depend on the test Mac's battery or memory pressure (E-6); test_power checks those."""
    if request.module.__name__.endswith("test_power"):
        return
    from dt3agent import power

    monkeypatch.setattr(power, "run", lambda argv: "")
