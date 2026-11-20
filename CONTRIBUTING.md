# Contributing

Thanks for your interest in improving mygns3theme!

## Getting started

1. Fork the repository and create a branch: `git checkout -b feat/my-change`.
2. Run the self-test (no GNS3 needed):

   ```sh
   python mygns3theme.py selftest --gns3-version 3.1.0a7 --gns3-version 2.2.61
   ```

3. Test on a real GNS3 install with the installer of your platform (`windows/install.cmd` or `unix/install.sh`), check the main window, *Preferences* and a project dialog, then run the matching uninstaller to make sure GNS3 is restored cleanly.

## Adding a theme

1. Copy a file of [`themes/`](themes) and fill in the Material 3 color roles (`primary`, `surface_container`, ...). Set `"mode"` to `"light"` or `"dark"`.
2. Optional: an `"overrides"` object can set any template token directly (for example `"font_size": "11pt"`).
3. Run `python scripts/make_previews.py` to generate its preview, and add it to the README gallery.

## Guidelines

- Keep the tool dependency-free (standard library only) and compatible with Python 3.10.
- Never weaken the safety checks: the bytecode verification and the backups must stay.
- Style changes go in [`template/style.qss`](template/style.qss); use `@token@` placeholders instead of hard-coded colors.
- Keep `unix/*.sh` compatible with the bash 3.2 shipped with macOS, and ShellCheck-clean.
- Update `CHANGELOG.md` under an `Unreleased` heading.

## Pull requests

- One topic per pull request, with a short description and before/after screenshots for visual changes.
- Mention the GNS3 version and the platform you tested with.

## Releasing (maintainers)

Bump `__version__` in `mygns3theme.py`, update the changelog, then push a tag:

```sh
git tag v2.0.0 && git push origin v2.0.0
```

The release workflow runs the self-test, builds both archives and publishes the GitHub release.

## Reporting bugs

Use the issue templates and include the output of `python mygns3theme.py status`.
