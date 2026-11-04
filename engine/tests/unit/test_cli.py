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
