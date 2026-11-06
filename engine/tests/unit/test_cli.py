from dt3agent import cli


def test_cli_maps_commands_to_rpc(monkeypatch, capsys):
    calls = []
    monkeypatch.setattr(cli.rpc, "call", lambda path, m, p: calls.append((m, p)) or {"ok": 1})
    assert cli.main(["status"]) == 0
    assert cli.main(["process", "x-devonthink-item://FB2DEBBE-8F8B-4049-8F4E-CE5FD12F20D8?page=1"]) == 0
    assert cli.main(["live", "off"]) == 0
    assert cli.main(["undo"]) == 0
    assert calls == [("status", {}), ("process", {"uuid": "FB2DEBBE-8F8B-4049-8F4E-CE5FD12F20D8"}),
                     ("live", {"on": False}), ("undo", {})]
    assert '"ok": 1' in capsys.readouterr().out


def test_cli_reports_engine_down(monkeypatch, capsys):
    def down(*a):
        raise cli.rpc.RPCError("engine_not_running")
    monkeypatch.setattr(cli.rpc, "call", down)
    assert cli.main(["status"]) == 1
    assert "engine_not_running" in capsys.readouterr().err


def test_process_without_record_uses_the_dt3_selection(monkeypatch):
    calls = []
    monkeypatch.setattr(cli.rpc, "call", lambda path, m, p: calls.append((m, p)) or {})
    assert cli.main(["process"]) == 0 and cli.main(["review"]) == 0
    assert calls == [("process_selected", {}), ("review", {})]


def test_ask_for_calibration(monkeypatch):
    calls = []
    monkeypatch.setattr(cli.rpc, "call", lambda path, m, p, timeout=120.0: calls.append((m, p, timeout)) or {})
    assert cli.main(["ask", "Was", "steht", "im", "Mietvertrag?"]) == 0
    assert calls == [("ask", {"question": "Was steht im Mietvertrag?"}, 600.0)]  # answers take a minute on the floor
