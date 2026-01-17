import pytest

from pathlib import Path
from gpsmax.ingest.garmin_ingest import iter_gpx_files

def test_iter_gpx_files_finds_only_garmin_gpx(tmp_path: Path):
    gvfs_root = tmp_path / "gvfs"
    gvfs_root.mkdir()

    # Non-Garmin tree (should be pruned)
    other = gvfs_root / "camera" / "DCIM"
    other.mkdir(parents=True)
    (other / "x.gpx").write_text("nope", encoding = "utf-8")

    # Garmin tree (should be walked)
    garmin = gvfs_root / "mtp:host=Garmin" / "Internal Storage" / "GARMIN" / "GPX" / "Current"
    garmin.mkdir(parents=True)
    (garmin / "Current.gpx").write_text("<gpx/>", encoding="utf-8")

    results = list(iter_gpx_files(gvfs_root))
    rels = [rel for _, rel in results]

    assert "mtp:host=Garmin/Internal Storage/GARMIN/GPX/Current/Current.gpx"
    assert all("DCIM" not in r for r in rels)
