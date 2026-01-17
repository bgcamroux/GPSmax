import pytest
import json
from pathlib import Path
from types import SimpleNamespace
import gpsmax.ingest.garmin_ingest as gi  # adjust import path

def test_main_ingests_and_writes_manifest(tmp_path: Path, monkeypatch):
    # Fake GVFS mount contents
    gvfs_root = tmp_path / "gvfs_mount"
    gpx_current = gvfs_root / "GARMIN" / "GPX" / "Current"
    gpx_current.mkdir(parents=True)
    (gpx_current / "Current.gpx").write_text("<gpx/>", encoding="utf-8")

    # Destination raw root
    raw_root = tmp_path / "raw"

    # Patch config loader to return raw_root
    monkeypatch.setattr(
        gi,
        "load_config",
        lambda: SimpleNamespace(paths=SimpleNamespace(raw_root=raw_root)),
    )

    # Patch MTP discovery to return our fake mount
    monkeypatch.setattr(
        gi,
        "discover_mtp_mount",
        lambda: gi.MtpMountInfo(
            mtp_uri="mtp:host=Garmin_Test",
            host="Garmin_Test",
            gvfs_mount=gvfs_root,
        ),
    )

    # Avoid calling real gio mount
    monkeypatch.setattr(gi, "ensure_mounted", lambda _uri: None)

    # Stable device id
    monkeypatch.setattr(gi, "derive_device_id", lambda _mtp: "DEVICE123")

    # Fix download date/year so the output path is deterministic
    monkeypatch.setattr(
        gi,
        "dt",
        gi.dt,  # keep module, but override now() if you prefer; simplest is CLI overrides below
    )

    # Run main with controlled args
    monkeypatch.setattr(
        gi.sys,
        "argv",
        ["garmin_ingest.py", "--download-date", "2025-04-26", "--year", "2025"],
    )

    rc = gi.main()
    assert rc == 0

    dest_base = raw_root / "2025" / "2025-04-26" / "DEVICE123"
    manifest_path = dest_base / "manifest.json"

    assert manifest_path.exists()
    doc = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert doc["counts"]["records"] == 1
    assert doc["files"][0]["category"] == "Current"
    assert doc["files"][0]["dest_relpath"].endswith("Current/Current.gpx")
