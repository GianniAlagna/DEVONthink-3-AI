"""E-6 power mode (SPEC §4.22): pause on battery and under memory pressure. macOS outputs are UNVERIFIED on 11."""
import pytest

from dt3agent.power import Power, parse_battery, parse_pressure

AC = "Now drawing from 'AC Power'\n -InternalBattery-0 (id=1234)\t100%; charged; 0:00 remaining present: true\n"
BATT = "Now drawing from 'Battery Power'\n -InternalBattery-0 (id=1234)\t87%; discharging; 4:10 remaining\n"
DESKTOP = "Now drawing from 'AC Power'\n"


def test_battery_parsing():
    assert parse_battery(AC) is False and parse_battery(BATT) is True and parse_battery(DESKTOP) is False
    assert parse_battery("") is None and parse_battery("garbage") is None


@pytest.mark.parametrize("out, level", [("1\n", 1), ("2", 2), ("4\n", 4), ("", None), ("x", None)])
def test_pressure_parsing(out, level):
    assert parse_pressure(out) == level


class Runner:
    def __init__(self, batt=AC, pressure="1"):
        self.batt, self.pressure, self.calls = batt, pressure, []

    def __call__(self, argv):
        self.calls.append(argv)
        return self.batt if argv[0] == "/usr/bin/pmset" else self.pressure


def test_hold_reasons_and_settings():
    r = Runner(batt=BATT, pressure="2")
    p = Power(r, clock=lambda: 0.0)
    assert p.hold({"pause_on_battery": True, "pause_on_memory_pressure": True}) == "battery"
    assert p.hold({"pause_on_battery": False, "pause_on_memory_pressure": True}) == "memory_pressure"
    assert p.hold({"pause_on_battery": False, "pause_on_memory_pressure": False}) is None
    # argv lists only, fixed system paths (no shell)
    assert ["/usr/bin/pmset", "-g", "batt"] in r.calls
    assert ["/usr/sbin/sysctl", "-n", "kern.memorystatus_vm_pressure_level"] in r.calls


def test_readings_are_cached_for_a_minute():
    now = [0.0]
    r = Runner()
    p = Power(r, clock=lambda: now[0])
    p.hold({}), p.hold({})
    assert len(r.calls) == 2
    now[0] = 61.0
    p.hold({})
    assert len(r.calls) == 4


def test_unknown_readings_never_hold():
    p = Power(lambda argv: "", clock=lambda: 0.0)
    assert p.hold({"pause_on_battery": True, "pause_on_memory_pressure": True}) is None
    assert p.state() == {"battery": None, "pressure": None}


def test_a_failing_command_never_holds():
    def boom(argv):
        raise OSError("no pmset")
    assert Power(boom, clock=lambda: 0.0).hold({}) is None


def test_service_holds_work_on_battery_and_reports_why(tmp_path):
    from dt3agent import config
    from dt3agent.service import Service
    from tests.fakes import FakeDT3, FakeLlamaServer, ai_reply

    uuid = "FB2DEBBE-8F8B-4049-8F4E-CE5FD12F20D8"
    server = FakeLlamaServer(reply=ai_reply(["Rechnung"]))
    cfg = config.load(tmp_path / "config.json")
    cfg["ai"]["url"] = server.url
    config.save(tmp_path / "config.json", cfg)
    svc = Service(tmp_path, FakeDT3({uuid: {"name": "x", "tags": [], "contentHash": "h", "text": "Rechnung"}}))
    try:
        svc.power = Power(Runner(batt=BATT), clock=lambda: 0.0)
        svc.handle("process", {"uuid": uuid})
        assert svc.tick() is None  # held: nothing processed
        st = svc.handle("status", {})
        assert st["power"] == {"battery": True, "pressure": 1, "held": "battery"} and st["queue"] == {"queued": 1}
        svc.handle("config_set", {"changes": {"power": {"pause_on_battery": False}}})
        assert svc.tick() == "planned"
    finally:
        svc.close()
        server.close()
