# GPSmax
A Python tool for managing, viewing, and analyzing GPX tracks with distance, speed, and elevation metrics.

## Description
GPSmax simplifies the consumer GPS workflow by connecting to and copying files from a (Garmin) GPS receiver to a fixed, immutable location on your path, cleaning up and reformatting GPX files to be human-readable with meaningful filenames, providing a simple report on track data, and viewing the track to determine further work.

This project began using shell scripts, but quickly grew in size to the point where moving to Python made the most sense. This is currently in *active development* using semantic versioning.

### Features

- Detect and connect to Garmin GPS receiver using `GVFS mount` for MTP devices.
- Discover and copy files from device to local filesystem (ingestion).
- Enter ingestion metadata into a SQLite database.
- Normalize files by cleaning them up to make them human readable with meaningful filenames.
- Use `fzf` to find and select files for processing.

## Requirements

Tested on Linux (EndeavourOS, Ubuntu) on Python >= 3.12.

`fzf` is not required but provides a substantial boost in user experience.

## Installation

```
git clone https://github.com/bgcamroux/GPSmax.git
cd gpsmax
pip install -e .[dev]
```

## Quick-Start



## Configuration
Configuration lives either in your local config folder (eg. `~/user/.config`) or in `gpxmax/config`. Configuration is loaded at runtime by using the `load_config` function.

Minimal example config:
```
[paths]
runtime_root = "~/GPS"
```

## Project Structure
```
src/
  gpsmax/
    analyze/       Analysis routines
    devices/       Device-specific routines
    formats/       GPX reading, parsing, writing
    ingest/        GPS ingestion and file download
    normalize/     Produce human readable files with meaningful names
    sql/           SQLite database
    util/          Helper functions useful in multiple areas
    visualize/     Track visualiztion
  tests/           Pytest-based testing suite
    data/          Test data
```

## Development & Testing
Currently only testing using `pytest`:

`pytest --cov=gpsmax'

## Contributing
Currently under sole-development. If you are interested in contributing, please contact the developer.

## License
This application is developed and released under the GPLv3 [license](LICENSE).