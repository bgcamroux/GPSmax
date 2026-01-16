import pytest

def test_analyze_sample_gpx(sample_gpx_path):
    from gpsmax.analyze.track import analyze_track

    stats = analyze_track(sample_gpx_path)

    assert stats["points"] == 211
    assert stats["segments"] == 210
    assert stats["distance_m"] == pytest.approx(1697.13, abs=1.0)
    assert stats["duration_s"] == 2088
    assert stats["avg_speed_mps"] == pytest.approx(0.813, abs=0.02)
    assert stats["max_speed_mps"] == pytest.approx(3.321, abs=0.02)
    
