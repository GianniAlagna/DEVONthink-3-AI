"""E-7 remote AI key (SPEC §4.22): read only from the macOS Keychain, never stored or logged by the engine.

The app writes the key with the Security framework; the engine reads it with `security find-generic-password -w`
(argv list; the key is on stdout, never in an argument). It is sent as `Authorization: Bearer` only to the
configured AI host, and only over https or to a loopback / private-network host, so it never travels in clear
text over the internet.
"""
import ipaddress
import subprocess
import urllib.parse

SERVICE = "codes.modular.dt3agent.ai"
ARGV = ["/usr/bin/security", "find-generic-password", "-s", SERVICE, "-w"]
MAX_KEY = 512


def _run(argv: list[str]) -> tuple[int, str]:
    p = subprocess.run(argv, capture_output=True, text=True, timeout=10, check=False)
    return p.returncode, p.stdout


def read_key(runner=None) -> str | None:
    try:
        code, out = (runner or _run)(ARGV)
    except (OSError, subprocess.SubprocessError):
        return None
    key = out.strip() if code == 0 else ""
    if not key or len(key) > MAX_KEY or not key.isprintable() or any(c.isspace() for c in key):
        return None
    return key


def may_send(url: str) -> bool:
    parts = urllib.parse.urlsplit(url)
    if parts.scheme == "https":
        return True
    host = (parts.hostname or "").lower()
    if host == "localhost" or host.endswith(".local"):
        return True
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    return ip.is_loopback or ip.is_private


def auth_headers(url: str, key: str | None) -> dict:
    return {"Authorization": f"Bearer {key}"} if key and may_send(url) else {}
