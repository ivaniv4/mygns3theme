# Contributing

Thanks for your interest in improving mygns3theme!

## Getting started

1. Fork the repository and create a branch: `git checkout -b feat/my-change`.
2. Use **Python 3.13** (the version bundled with GNS3 3.1) and a GNS3 3.1 install on Windows.
3. Test on a real GNS3 install: run `install.ps1`, start GNS3, check the main window, *Preferences* and a project dialog.
4. Run `uninstall.ps1` afterwards to make sure GNS3 is restored cleanly.

## Guidelines

- Keep the tool dependency-free (standard library only).
- Never weaken the safety checks: the bytecode verification and the backup must stay.
- Style changes go in `theme/violet.qss`; keep colors as `@palette_key@` tokens instead of hard-coded values.
- Add new palette keys to `theme/palette.json` **and** document them in the README.
- Update `CHANGELOG.md` under an `Unreleased` heading.

## Pull requests

- One topic per pull request, with a short description and before/after screenshots for visual changes.
- Mention the GNS3 version you tested with.

## Reporting bugs

Use the issue templates and include the output of `py -3.13 mygns3theme.py status`.
