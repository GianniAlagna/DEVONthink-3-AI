"""Client for the Vision helper `dt3agent-vision` (ADR-0006, SPEC §4.15).

The helper reads the record's file and returns text or QR payloads; both are used for analysis only (brief A1).
Arguments are passed as a list (no shell); errors come back as short codes, never file content.
"""
import base64
import binascii
import json
import subprocess
from pathlib import Path


class VisionError(RuntimeError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


class VisionClient:
    def __init__(self, helper: str, languages: list[str], max_pages: int = 5, timeout: float = 180.0):
        self.helper, self.languages, self.max_pages, self.timeout = helper, languages, max_pages, timeout

    def ocr(self, path: str) -> str:
        out = self._run("ocr", path, [",".join(self.languages), str(self.max_pages)])
        try:
            return str(out["text"])
        except (KeyError, TypeError):
            raise VisionError("ocr_bad_output") from None

    def qr(self, path: str) -> list[str]:
        """Text of every QR code on the first pages (B-1). The helper sends bytes as base64, so CR LF and
        any other byte survive the trip; payloads that are not UTF-8 text cannot be a QR-bill and are skipped."""
        out = self._run("qr", path, [str(self.max_pages)])
        payloads = out.get("payloads") if isinstance(out, dict) else None
        if not isinstance(payloads, list):
            raise VisionError("qr_bad_output")
        texts = []
        for p in payloads:
            try:
                raw = base64.b64decode(p, validate=True)
            except (binascii.Error, TypeError, ValueError):
                raise VisionError("qr_bad_output") from None
            try:
                texts.append(raw.decode("utf-8"))
            except UnicodeDecodeError:
                continue
        return texts

    def _run(self, mode: str, path: str, extra: list[str]):
        if not path or not Path(path).is_file():
            raise VisionError(f"{mode}_no_file")
        try:
            out = subprocess.run([self.helper, mode, path, *extra],
                                 capture_output=True, timeout=self.timeout, check=False)
        except subprocess.TimeoutExpired:
            raise VisionError(f"{mode}_timeout") from None
        except OSError:
            raise VisionError(f"{mode}_unavailable") from None
        if out.returncode != 0:
            raise VisionError(f"{mode}_failed")
        try:
            return json.loads(out.stdout)
        except ValueError:
            raise VisionError(f"{mode}_bad_output") from None
