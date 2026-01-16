from pathlib import Path
import pytest


@pytest.fixture
def sample_gpx_path() -> Path:
    return Path(__file__).parent / "data" / "sample.gpx"
