import pytest

from types import SimpleNamespace
import gpsmax.ingest.garmin_ingest as gi

def test_ensure_mounted_calls_gio_mount(monkeypatch):
    calls = []

    def fake_run(cmd, check=False):
        calls.append((cmd, check))
        return SimpleNamespace(returncode=0, stderr="")

    monkeypatch.setattr(gi, "run", fake_run)

    gi.ensure_mounted("mtp:host=Garmin/")
    assert calls == [(["gio", "mount", "mtp:host=Garmin/"], False)]
