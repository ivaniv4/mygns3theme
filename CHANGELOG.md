# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project adheres to [Semantic Versioning](https://semver.org/).

## [1.0.0] - 2026-11-20

### Added
- Material 3 "Violet" style for the GNS3 3.1 desktop GUI on Windows.
- `mygns3theme.py` CLI: `patch`, `unpatch`, `apply`, `reset-style`, `status`.
- Verification of official `gns3-gui` sources against the shipped bytecode before patching.
- Automatic backup and restore of `library.zip`.
- Customizable palette (`theme/palette.json`) and Qt style sheet (`theme/violet.qss`).
- Toolbar icon tinting.
- `install.ps1` and `uninstall.ps1` with UAC elevation.
