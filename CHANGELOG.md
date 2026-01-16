# Changelog

All notable changes to this project will be documented in this file.
This changelog was prepared from the repository commit history and curated into milestone releases.

The format follows "Keep a Changelog" with an "Unreleased" section for ongoing work.

## [Unreleased]
No notable user-facing changes recorded yet.

---

## [0.1.0] - 2026-01-16
Initial public release combining the work completed through 2026-01-16.

### Added
- Unit test scaffold and GitHub Actions workflow. ([commit c65eee8](https://github.com/bgcamroux/GPSmax/commit/c65eee8067f82000961d85c22c1781c99a0be2fa))
- Project dependency on the `haversine` package. ([commit 7fd722c](https://github.com/bgcamroux/GPSmax/commit/7fd722cc3920c2bd9c163af758caa40e19e8162e))
- Reusable fzf selection module (refactor). ([commit 83f0028](https://github.com/bgcamroux/GPSmax/commit/83f0028b7beced97f9faeca4dad1d06afff32896), [commit 5522618](https://github.com/bgcamroux/GPSmax/commit/552261895b62df91be3ff6664453dda82c8ce01a))
- Allow sample data files named `sample*.gpx` to be tracked (update to .gitignore rules). ([commit a484a82](https://github.com/bgcamroux/GPSmax/commit/a484a8201fb13eb93fba7e43da78918e6a64525a))

### Changed
- Naming templates and deterministic naming support introduced. ([commit 2487355](https://github.com/bgcamroux/GPSmax/commit/2487355fb0afc1af8068a887347635c83bb297f9))
- Improvements to fzf UX: show filenames only in the list and show track/route/waypoint previews. ([commit ee4ff06](https://github.com/bgcamroux/GPSmax/commit/ee4ff06960440428b5c1f07fb50a358a7afbe6ea))

### Fixed
- Fixes for normalization path and filename handling. ([commit eb52d77](https://github.com/bgcamroux/GPSmax/commit/eb52d77c3a6bf17a3cbc59ebf8a3648f3543d945))
- Typo fixes in `gpx.py`. ([commit cc926ed](https://github.com/bgcamroux/GPSmax/commit/cc9267ed30419342be9cbe8c2d0d95876c094732))

---

## [0.0.2] - 2026-01-13
Stability and layout milestone: reorganised the codebase to a package layout and improved import/run experience.

### Added
- Make `normalize`, `ingest`, and `sql` runnable as modules. ([commit 78d7a9e](https://github.com/bgcamroux/GPSmax/commit/78d7a9ee80ca6a423f7919d589a3a782a010da59))

### Changed
- Adopt `src/` package layout. ([commit d3904b0](https://github.com/bgcamroux/GPSmax/commit/d3904b056f475638b7c196ae7e5022abfccccf70))
- Tweak imports to ensure subpackage imports work smoothly. ([commit 1854e4e](https://github.com/bgcamroux/GPSmax/commit/1854e4eb54db60e3605f5e0a687949f14855485b))

### Other
- Refactor GPX helper code into modules and update callers. ([commit b0a6297](https://github.com/bgcamroux/GPSmax/commit/b0a62972fc37a569c3e6404065023ea2fe192d6c))
- Add `*.geany` to ignore list. ([commit fbc2025](https://github.com/bgcamroux/GPSmax/commit/fbc202551f779f863fe9023393a62bf49c4ec5d8))

---

## [0.0.1] - 2026-01-09
Initial Python rewrite / foundation for ingestion and normalization.

### Added
- Project initialization for ingestion & SQLite (Phase A). ([commit 756668e](https://github.com/bgcamroux/GPSmax/commit/756668ed674ef613857d6812f238ae09944fc09f))
- Normalization script and documentation (enter Phase B). ([commit f1e22d8](https://github.com/bgcamroux/GPSmax/commit/f1e22d88bc303a4e5f653e09e4496f76b0f82cee))
- TrackPoint dataclass and `extract_trackpoints()` helper. ([commit 74edfe7](https://github.com/bgcamroux/GPSmax/commit/74edfe71da318ae4239f05f0afeed15ea0598ee6))

### Docs
- Add initial ROADMAP and update phase numbering. ([commits 578f8f2, 788c986, 8027013](https://github.com/bgcamroux/GPSmax/commits))
