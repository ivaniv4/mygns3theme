# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project adheres to [Semantic Versioning](https://semver.org/).

## [2.1.0] - 2026-11-20

### Added
- Support for older GNS3 versions, from 2.0 to 3.0.5 (PyQt5 builds), next to the PyQt6 ones.
- Python 3.7 and 3.8 builds are recognized, and the tool itself runs on Python 3.8+.
- `tests/qt_styles.py`: runs the patched style code of 9 GNS3 versions on a real PyQt5 and PyQt6, for every theme.
- The self-test now covers 8 GNS3 versions, and CI runs it on Python 3.8 too.

### Fixed
- Downloads of the official GNS3 sources are retried with a delay on rate limits (HTTP 429) and server errors (5xx), which made CI fail with a 503.
- The patched style code no longer assumes `QtWidgets`, grid colors or the console exist (they are missing in old versions).

## 2.0.0 - 2026-11-20

### Added
- **Linux and macOS support**: pip / distribution installs (`.py` sources) and the macOS `GNS3.app` bundle (`.pyc`, re-signed after patching).
- **8 new themes** matching the GNS3 Web UI: Deep Purple & Amber, Indigo & Pink, Magenta & Violet, Rose & Red (light) and Pink & Bluegrey, Purple & Green, Azure & Blue, Cyan & Orange (dark).
- Dark theme support (light topology labels, charcoal icons).
- Every installed theme appears in *Edit > Preferences > General > Interface style*.
- One-step installers per platform: `install.cmd` / `install.ps1` (Windows) and `install.sh` (Linux/macOS), with Python detection or installation, theme picker and automatic GNS3 shutdown and restart.
- Two release archives (`-windows.zip`, `-linux-macos.tar.gz`) built by `scripts/build_release.py` and published by GitHub Actions on every `v*` tag.
- `detect`, `list`, `select`, `remove-themes` and `selftest` commands.
- CI: self-test on Windows, Linux and macOS, ShellCheck and PowerShell syntax checks.
- Theme previews in `docs/themes/` (`scripts/make_previews.py`).

### Changed
- Themes are plain JSON files using Material 3 color roles (`themes/*.json`); the style sheet template moved to `template/style.qss`.
- Backups are refreshed automatically after a GNS3 upgrade.

### Removed
- The 1.x Violet style, replaced by the Web UI themes.

### Migration
- An install patched by 1.x is detected and upgraded in place by the 2.0 installer, and switches to Deep Purple & Amber.

## 1.0.0 - 2026-11-20

### Added
- Material 3 "Violet" style for the GNS3 3.1 desktop GUI on Windows.
- `mygns3theme.py` CLI: `patch`, `unpatch`, `apply`, `reset-style`, `status`.
- Verification of official `gns3-gui` sources against the shipped bytecode before patching.
- Automatic backup and restore of `library.zip`.
- Toolbar icon tinting.

[2.1.0]: https://github.com/ivaniv4/mygns3theme/releases/tag/v2.1.0
