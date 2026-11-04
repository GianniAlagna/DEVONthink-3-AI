"""Client for the Vision helper `dt3agent-vision` (ADR-0006, SPEC §4.15).

The helper reads the record's file and returns text; the text is used for analysis only (brief A1).
Arguments are passed as a list (no shell); errors come back as short codes, never file content.
"""
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
        if not path or not Path(path).is_file():
            raise VisionError("ocr_no_file")
        try:
            out = subprocess.run([self.helper, "ocr", path, ",".join(self.languages), str(self.max_pages)],
                                 capture_output=True, timeout=self.timeout, check=False)
        except subprocess.TimeoutExpired:
            raise VisionError("ocr_timeout") from None
        except OSError:
            raise VisionError("ocr_unavailable") from None
        if out.returncode != 0:
            raise VisionError("ocr_failed")
        try:
            return str(json.loads(out.stdout)["text"])
        except (ValueError, KeyError, TypeError):
            raise VisionError("ocr_bad_output") from None
