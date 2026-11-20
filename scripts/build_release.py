#!/usr/bin/env python3
"""
Builds the two release archives in dist/:

    mygns3theme-<version>-windows.zip       install.cmd / install.ps1 at the root
    mygns3theme-<version>-linux-macos.tar.gz install.sh at the root

Usage: python scripts/build_release.py [version]   (default: mygns3theme.__version__)
"""

import io
import re
import sys
import tarfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"

# files shared by both releases (folders are copied recursively)
COMMON = ["mygns3theme.py", "patches", "template", "themes", "README.md", "LICENSE", "CHANGELOG.md"]
PLATFORMS = {
    "windows": {
        "windows/install.cmd": "install.cmd",
        "windows/install.ps1": "install.ps1",
        "windows/uninstall.cmd": "uninstall.cmd",
        "windows/uninstall.ps1": "uninstall.ps1",
    },
    "linux-macos": {
        "unix/install.sh": "install.sh",
        "unix/uninstall.sh": "uninstall.sh",
    },
}
EXECUTABLE = {"install.sh", "uninstall.sh", "mygns3theme.py"}


def tool_version():
    text = (ROOT / "mygns3theme.py").read_text(encoding="utf-8")
    return re.search(r'^__version__ = "([^"]+)"', text, flags=re.MULTILINE).group(1)


def files_for(platform):
    """(source path, path inside the archive) pairs."""
    pairs = []
    for name in COMMON:
        source = ROOT / name
        if source.is_dir():
            pairs += [(f, f.relative_to(ROOT).as_posix()) for f in sorted(source.rglob("*"))
                      if f.is_file() and "__pycache__" not in f.parts]
        else:
            pairs.append((source, name))
    pairs += [(ROOT / src, dst) for src, dst in PLATFORMS[platform].items()]
    return pairs


def build_zip(path, prefix, pairs):
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for source, name in pairs:
            z.write(source, f"{prefix}/{name}")


def build_tar(path, prefix, pairs):
    with tarfile.open(path, "w:gz") as tar:
        for source, name in pairs:
            data = source.read_bytes()
            if source.suffix in (".sh", ".py"):
                data = data.replace(b"\r\n", b"\n")  # shell scripts must keep LF endings
            entry = tarfile.TarInfo(f"{prefix}/{name}")
            entry.size = len(data)
            entry.mode = 0o755 if Path(name).name in EXECUTABLE else 0o644
            entry.mtime = int(source.stat().st_mtime)
            tar.addfile(entry, io.BytesIO(data))


def main():
    version = (sys.argv[1] if len(sys.argv) > 1 else tool_version()).lstrip("v")
    DIST.mkdir(exist_ok=True)
    for platform in PLATFORMS:
        prefix = f"mygns3theme-{version}-{platform}"
        pairs = files_for(platform)
        if platform == "windows":
            archive = DIST / f"{prefix}.zip"
            build_zip(archive, prefix, pairs)
        else:
            archive = DIST / f"{prefix}.tar.gz"
            build_tar(archive, prefix, pairs)
        print(f"{archive.relative_to(ROOT)}  ({len(pairs)} files)")


if __name__ == "__main__":
    main()
