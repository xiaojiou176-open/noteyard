import builtins
from pathlib import Path

import notes_recovery.services.wizard as wizard


def test_run_wizard_flow(monkeypatch, tmp_path: Path) -> None:
    responses = iter([
        str(tmp_path / "out"),
        "Alpha",
        "y",  # include core spotlight
        "y",  # include notes cache
        "y",  # run wal
        "y",  # run query
        "y",  # run carve
        "y",  # run recover
        "y",  # run protobuf
        "y",  # run spotlight parse
        "y",  # run plugins
        "y",  # generate report
        "y",  # run verify
        "y",  # recover ignore freelist
        "lost_and_found",
        "",   # plugins config
        "y",  # plugins enable all
        "20", # report max items
        "5",  # carve max hits
        "20", # carve min text len
        "0.6",# carve min text ratio
        "3",  # protobuf max notes
        "1",  # protobuf max zdata mb
        "10", # spotlight max files
        "1024", # spotlight max bytes
        "3",  # spotlight min string len
        "2000", # spotlight max chars
        "200", # spotlight max rows
        "5",  # verify top n
        "120",# verify preview len
        "y",  # verify deep
        "y",  # verify deep all
        "0",  # verify deep max mb
        "10", # verify deep max hits
        "n",  # verify match all
        "y",  # verify fuzzy
        "0.7",# verify fuzzy threshold
        "2.0",# verify fuzzy boost
        "500",# verify fuzzy max len
        "y",  # confirm run
    ])

    monkeypatch.setattr(builtins, "input", lambda _prompt="": next(responses))

    calls = []

    def fake_auto_run(*args, **kwargs):
        calls.append((args, kwargs))

    monkeypatch.setattr(wizard, "auto_run", fake_auto_run)

    wizard.run_wizard()
    assert calls
