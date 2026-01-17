import pytest
from gpsmax.ingest.garmin_ingest import classify_gpx

@pytest.mark.parametrize(
    "relpath, expected",
    [
        ("/GARMIN/GPX/Current/Current.gpx", ("Current", "Current.gpx")),
        ("/GARMIN/GPX/Archive/2025/track.gpx", ("Archive", "2025/track.gpx")),
        ("/GARMIN/GPX/Waypoints_2025-01-01.gpx", ("Waypoints", "Waypoints_2025-01-01.gpx")),
        ("/GARMIN/GPX/something_else.gpx", ("Other", "something_else.gpx")),
        ("/NOTGARMIN/GPX/foo.gpx", ("Skip", None)),
        ("/GARMIN/Activities/foo.fit", ("Skip", None)),
    ],
)
def test_classify_gpx(relpath, expected):
    assert classify_gpx(relpath) == expected
