"""Power mode (SPEC §4.22, E-6): hold work on battery and under memory pressure (brief §2.4).

Readings come from fixed system tools, run with an argument list (no shell), cached for a minute.
macOS 11 output formats are UNVERIFIED until the Phase 7 floor check; anything unreadable never holds.
"""
import re
import subprocess
import time

PMSET = ["/usr/bin/pmset", "-g", "batt"]
PRESSURE = ["/usr/sbin/sysctl", "-n", "kern.memorystatus_vm_pressure_level"]  # 1 normal, 2 warn, 4 critical
CACHE_S = 60.0


def run(argv: list[str]) -> str:
    return subprocess.run(argv, capture_output=True, text=True, timeout=5, check=False).stdout


def parse_battery(out: str) -> bool | None:
    m = re.search(r"drawing from '([^']+)'", out)
    if not m:
        return None
    return m.group(1).strip().lower().startswith("battery")


def parse_pressure(out: str) -> int | None:
    out = out.strip()
    return int(out) if out.isdigit() else None


class Power:
    def __init__(self, runner=None, clock=time.monotonic):
        self.runner, self.clock = runner, clock
        self._at, self._state = None, {"battery": None, "pressure": None}

    def _read(self, argv, parse):
        try:
            return parse((self.runner or run)(argv))  # module-level run, looked up at call time
        except (OSError, subprocess.SubprocessError, ValueError):
            return None

    def state(self) -> dict:
        now = self.clock()
        if self._at is None or now - self._at >= CACHE_S:
            self._state = {"battery": self._read(PMSET, parse_battery),
                           "pressure": self._read(PRESSURE, parse_pressure)}
            self._at = now
        return dict(self._state)

    def hold(self, settings: dict) -> str | None:
        """Why work should wait now ('battery', 'memory_pressure') or None."""
        s = self.state()
        if settings.get("pause_on_battery", True) and s["battery"] is True:
            return "battery"
        if settings.get("pause_on_memory_pressure", True) and (s["pressure"] or 0) >= 2:
            return "memory_pressure"
        return None
