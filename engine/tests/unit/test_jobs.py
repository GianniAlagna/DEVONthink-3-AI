"""J-2 scheduler (SPEC §4.21): due times, once per due time, catch-up once, never two at once."""
from datetime import datetime, timedelta, timezone

import pytest

from dt3agent import config, jobs, store

TZ = timezone(timedelta(hours=1))  # CET
NIGHTLY = {"enabled": True, "time": "02:30"}
DIGEST = {"enabled": True, "day": "mon", "time": "07:30"}


def at(y, mo, d, h, mi):
    return datetime(y, mo, d, h, mi, tzinfo=TZ)


def sched():
    return jobs.Scheduler(store.open_db(":memory:", jobs.MIGRATIONS))


@pytest.mark.parametrize("now,spec,expected", [
    (at(2026, 11, 6, 3, 0), NIGHTLY, at(2026, 11, 6, 2, 30)),     # after today's time: today
    (at(2026, 11, 6, 2, 0), NIGHTLY, at(2026, 11, 5, 2, 30)),     # before: yesterday
    (at(2026, 11, 6, 2, 30), NIGHTLY, at(2026, 11, 6, 2, 30)),    # exactly at the time
    (at(2026, 11, 6, 9, 0), DIGEST, at(2026, 11, 2, 7, 30)),      # Friday → last Monday
    (at(2026, 11, 9, 7, 0), DIGEST, at(2026, 11, 2, 7, 30)),      # Monday before the time → a week back
    (at(2026, 11, 9, 8, 0), DIGEST, at(2026, 11, 9, 7, 30)),      # Monday after the time → today
])
def test_last_due(now, spec, expected):
    assert jobs.last_due(spec, now) == expected


def test_first_start_sets_a_baseline_and_runs_nothing():
    s = sched()
    assert s.due({"nightly": NIGHTLY}, at(2026, 11, 6, 9, 0)) == []  # no run right after install


def test_runs_once_per_due_time():
    s = sched()
    cfg = {"nightly": NIGHTLY}
    s.due(cfg, at(2026, 11, 6, 9, 0))                           # baseline
    assert s.due(cfg, at(2026, 11, 7, 1, 0)) == []              # before tonight's time
    assert s.due(cfg, at(2026, 11, 7, 2, 31)) == ["nightly"]
    s.done("nightly", at(2026, 11, 7, 2, 31), "ok")
    assert s.due(cfg, at(2026, 11, 7, 2, 45)) == []             # not twice for the same due time


def test_missed_days_run_once_not_once_per_day():
    s = sched()
    cfg = {"nightly": NIGHTLY}
    s.due(cfg, at(2026, 11, 1, 9, 0))
    assert s.due(cfg, at(2026, 11, 6, 9, 0)) == ["nightly"]     # Mac asleep for 5 nights
    s.done("nightly", at(2026, 11, 6, 9, 0), "ok")
    assert s.due(cfg, at(2026, 11, 6, 9, 5)) == []


def test_disabled_jobs_are_never_due():
    s = sched()
    cfg = {"nightly": dict(NIGHTLY, enabled=False)}
    s.due(cfg, at(2026, 11, 1, 9, 0))
    assert s.due(cfg, at(2026, 11, 6, 9, 0)) == []


def test_a_failed_run_is_not_repeated_until_the_next_due_time():
    s = sched()
    cfg = {"nightly": NIGHTLY}
    s.due(cfg, at(2026, 11, 5, 9, 0))
    assert s.due(cfg, at(2026, 11, 6, 3, 0)) == ["nightly"]
    s.done("nightly", at(2026, 11, 6, 3, 0), "dt3_unreachable")
    assert s.due(cfg, at(2026, 11, 6, 4, 0)) == []
    assert s.last("nightly")["result"] == "dt3_unreachable"


def test_several_due_jobs_come_in_a_fixed_order():
    s = sched()
    cfg = {"digest": DIGEST, "nightly": NIGHTLY}
    s.due(cfg, at(2026, 11, 1, 9, 0))
    assert s.due(cfg, at(2026, 11, 9, 9, 0)) == ["nightly", "digest"]


@pytest.mark.parametrize("bad", [
    {"nightly": {"enabled": True, "time": "25:00"}},
    {"nightly": {"enabled": "yes", "time": "02:30"}},
    {"digest": {"enabled": True, "day": "montag", "time": "07:30"}},
    {"unknown": {"enabled": True, "time": "02:30"}},
    {"nightly": {"enabled": True, "time": "02:30", "extra": 1}},
])
def test_bad_jobs_config_is_refused(bad):
    with pytest.raises(config.ConfigError):
        config.merge(config.DEFAULTS, {"jobs": bad})


def test_defaults_are_valid_and_digest_hygiene_off():
    cfg = config.validate(config.merge(config.DEFAULTS, {}))
    assert cfg["jobs"]["nightly"]["enabled"] is True
    assert cfg["jobs"]["digest"]["enabled"] is False and cfg["jobs"]["hygiene"]["enabled"] is False


def service(tmp_path, nightly_at="02:30"):
    from dt3agent.service import Service
    from tests.fakes import FakeDT3
    svc = Service(tmp_path, FakeDT3())
    svc.cfg["jobs"]["nightly"]["time"] = nightly_at
    return svc


def test_service_runs_a_due_job_once_and_reports_it(tmp_path):
    svc = service(tmp_path)
    runs = []
    svc.job_runners["nightly"] = lambda: runs.append(1) or "ok"
    svc.local_clock = lambda: at(2026, 11, 5, 9, 0)
    assert svc.tick() is None                                    # baseline only
    svc.local_clock = lambda: at(2026, 11, 6, 2, 31)
    assert svc.tick() == "job:nightly:ok"
    assert svc.tick() is None and runs == [1]
    assert svc.handle("status", {})["jobs"]["nightly"]["result"] == "ok"


def test_service_holds_jobs_while_paused(tmp_path):
    svc = service(tmp_path)
    svc.job_runners["nightly"] = lambda: "ok"
    svc.local_clock = lambda: at(2026, 11, 5, 9, 0)
    svc.tick()
    svc.handle("pause", {})
    svc.local_clock = lambda: at(2026, 11, 6, 2, 31)
    assert svc.tick() is None
    svc.handle("resume", {})
    assert svc.tick() == "job:nightly:ok"


def test_a_failing_job_keeps_only_a_code(tmp_path):
    from dt3agent.bridge import BridgeError
    svc = service(tmp_path)

    def boom():
        raise BridgeError("dt3_unreachable")

    def leak():
        raise ValueError("Kontostand CHF 4'250.00")

    svc.job_runners["nightly"] = boom
    svc.local_clock = lambda: at(2026, 11, 5, 9, 0)
    svc.tick()
    svc.local_clock = lambda: at(2026, 11, 6, 2, 31)
    assert svc.tick() == "job:nightly:dt3_unreachable"
    svc.job_runners["nightly"] = leak
    svc.local_clock = lambda: at(2026, 11, 7, 2, 31)
    assert svc.tick() == "job:nightly:job_failed"
