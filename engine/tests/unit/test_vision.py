"""P3-8 Vision OCR hook: the client against a stand-in helper, and the pipeline fallback."""
import json
import stat

import pytest

from dt3agent.vision import VisionClient, VisionError


def helper(tmp_path, body):
    h = tmp_path / "dt3agent-vision"
    h.write_text("#!/bin/sh\n" + body + "\n")
    h.chmod(h.stat().st_mode | stat.S_IXUSR)
    return str(h)


@pytest.fixture
def scan(tmp_path):
    f = tmp_path / "scan.pdf"
    f.write_bytes(b"%PDF-1.4 fake")
    return str(f)


def test_ocr_returns_text_and_passes_arguments_as_a_list(tmp_path, scan):
    args_file = tmp_path / "args"
    reply = '{"pages": 1, "text": "Rechnung 4711", "ms": 5}'
    h = helper(tmp_path, f'printf "%s\\n" "$@" > {args_file}; echo \'{reply}\'')
    assert VisionClient(h, ["de-DE", "fr-FR"], max_pages=3).ocr(scan) == "Rechnung 4711"
    assert args_file.read_text().split("\n")[:4] == ["ocr", scan, "de-DE,fr-FR", "3"]


@pytest.mark.parametrize("body, code", [
    ("echo unreadable >&2; exit 1", "ocr_failed"),
    ("echo not-json", "ocr_bad_output"),
    ("sleep 5", "ocr_timeout"),
])
def test_helper_failures_give_codes(tmp_path, scan, body, code):
    with pytest.raises(VisionError) as e:
        VisionClient(helper(tmp_path, body), ["de-DE"], timeout=1).ocr(scan)
    assert e.value.code == code


def test_missing_helper_or_file(tmp_path, scan):
    with pytest.raises(VisionError) as e:
        VisionClient(str(tmp_path / "nope"), ["de-DE"]).ocr(scan)
    assert e.value.code == "ocr_unavailable"
    with pytest.raises(VisionError) as e:
        VisionClient(str(tmp_path / "nope"), ["de-DE"]).ocr(str(tmp_path / "missing.pdf"))
    assert e.value.code == "ocr_no_file"


def b64(text):
    import base64
    return base64.b64encode(text.encode()).decode()


def test_qr_returns_decoded_payloads_and_passes_arguments(tmp_path, scan):
    # B-1: payloads come back byte-exact (base64), the client decodes UTF-8 text for the QR-bill parser
    args_file = tmp_path / "args"
    payload = "SPC\r\n0200\r\n1\r\nCH4431999123000889012"  # CR LF kept as sent
    reply = json.dumps({"payloads": [b64(payload), b64("https://example.org")], "ms": 5})
    h = helper(tmp_path, f'printf "%s\\n" "$@" > {args_file}; echo \'{reply}\'')
    assert VisionClient(h, ["de-DE"], max_pages=2).qr(scan) == [payload, "https://example.org"]
    assert args_file.read_text().split("\n")[:3] == ["qr", scan, "2"]


def test_qr_none_found_is_an_empty_list(tmp_path, scan):
    assert VisionClient(helper(tmp_path, 'echo \'{"payloads": [], "ms": 1}\''), ["de-DE"]).qr(scan) == []


@pytest.mark.parametrize("body, code", [
    ("echo render_failed >&2; exit 1", "qr_failed"),
    ("echo not-json", "qr_bad_output"),
    ("echo \'{\"payloads\": [\"%%%\"]}\'", "qr_bad_output"),
    ("echo \'{\"payloads\": \"x\"}\'", "qr_bad_output"),
    ("sleep 5", "qr_timeout"),
])
def test_qr_failures_give_codes(tmp_path, scan, body, code):
    with pytest.raises(VisionError) as e:
        VisionClient(helper(tmp_path, body), ["de-DE"], timeout=1).qr(scan)
    assert e.value.code == code


def test_qr_skips_payloads_that_are_not_text(tmp_path, scan):
    import base64
    bad = base64.b64encode(b"\xff\xfe\x00").decode()
    reply = json.dumps({"payloads": [bad, b64("SPC")]})
    assert VisionClient(helper(tmp_path, f"echo '{reply}'"), ["de-DE"]).qr(scan) == ["SPC"]


def test_qr_missing_helper_or_file(tmp_path, scan):
    with pytest.raises(VisionError) as e:
        VisionClient(str(tmp_path / "nope"), ["de-DE"]).qr(scan)
    assert e.value.code == "qr_unavailable"
    with pytest.raises(VisionError) as e:
        VisionClient(str(tmp_path / "nope"), ["de-DE"]).qr(str(tmp_path / "missing.pdf"))
    assert e.value.code == "qr_no_file"


def test_pipeline_uses_ocr_for_records_without_text(tmp_path):
    from dt3agent import store
    from dt3agent.adapter import DT3Adapter
    from dt3agent.audit import AuditLog
    from dt3agent.pipeline import MIGRATIONS, Pipeline
    from dt3agent.undo import MIGRATIONS as UNDO
    from dt3agent.undo import UndoJournal
    from tests.fakes import FakeDT3
    from tests.unit.test_pipeline import A, FakeAI

    class FakeVision:
        def __init__(self, text=None, error=None):
            self.text, self.error, self.paths = text, error, []

        def ocr(self, path):
            self.paths.append(path)
            if self.error:
                raise VisionError(self.error)
            return self.text

    dt3 = FakeDT3({A: {"name": "scan.pdf", "tags": [], "contentHash": "h", "text": "", "path": "/db/scan.pdf"}})
    con = store.open_db(tmp_path / "e.db", MIGRATIONS)
    adapter = DT3Adapter(dt3, UndoJournal(store.open_db(tmp_path / "u.db", UNDO)), AuditLog(tmp_path / "a"))
    ai, vision = FakeAI(["Rechnung"]), FakeVision("Rechnung Nr. 4711")
    out = Pipeline(adapter, ai, con, dry_run=True, vision=vision).process(A, batch_id="b1")
    assert out.status == "planned" and vision.paths == ["/db/scan.pdf"] and ai.calls == 1
    out = Pipeline(adapter, ai, con, dry_run=True, vision=FakeVision(error="ocr_failed")).process(A, batch_id="b2")
    assert (out.status, out.code) == ("review", "ocr_failed")
    out = Pipeline(adapter, ai, con, dry_run=True, vision=FakeVision("   ")).process(A, batch_id="b3")
    assert (out.status, out.code) == ("review", "no_text")
    assert json.dumps(dt3.records[A]["tags"]) == "[]"
