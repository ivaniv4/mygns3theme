#!/usr/bin/env python3
"""
mygns3theme - a violet Material 3 style for the GNS3 desktop GUI on Windows.

Adapted from gns3theme (https://github.com/dilmun/gns3theme, MIT license).
gns3theme patches the GUI .py/.pyc files on Linux and macOS; the Windows build
of GNS3 is frozen with cx_Freeze, so its modules are .pyc files packed in
lib\\library.zip. This tool rebuilds the three modules it needs (settings,
main_window, style) from the official gns3-gui sources of the installed
version, after checking that those sources compile to exactly the bytecode
GNS3 ships, then writes them back into library.zip (keeping a backup).

Commands:
    patch       add the "Violet" style to GNS3 (needs an elevated prompt)
    unpatch     restore the original library.zip (needs an elevated prompt)
    apply       render the theme into %APPDATA%\\GNS3\\mygns3theme and select it
    reset-style switch GNS3 back to the Classic style
    status      show what is installed

Must run with the same Python minor version as GNS3 (3.13 for GNS3 3.1).
"""

import argparse
import importlib.util
import json
import marshal
import os
import re
import shutil
import subprocess
import sys
import urllib.request
import winreg
import zipfile
from pathlib import Path

STYLE_NAME = "Violet"
PATCH_MARKER = b"setVioletStyle"
MODULES = ("settings", "main_window", "style")
SOURCE_URL = "https://raw.githubusercontent.com/GNS3/gns3-gui/v{version}/gns3/{module}.py"

REPO_DIR = Path(__file__).resolve().parent
THEME_SRC = REPO_DIR / "theme"
STYLE_PATCH = REPO_DIR / "patches" / "style_violet.py"
CACHE_DIR = REPO_DIR / "cache"
DEFAULT_GNS3_DIR = Path(os.environ.get("ProgramW6432", os.environ.get("ProgramFiles", r"C:\Program Files"))) / "GNS3"
GNS3_APPDATA = Path(os.environ["APPDATA"]) / "GNS3"
THEME_DIR = GNS3_APPDATA / "mygns3theme"


def info(msg):
    print(f"[mygns3theme] {msg}")


def fail(msg):
    print(f"[mygns3theme] ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


# --- GNS3 installation ---

def installed_version():
    """Return the GNS3 version from the Windows uninstall registry entries."""
    uninstall = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"
    for view in (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY):
        try:
            root = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, uninstall, 0, winreg.KEY_READ | view)
        except OSError:
            continue
        with root:
            for i in range(winreg.QueryInfoKey(root)[0]):
                try:
                    with winreg.OpenKey(root, winreg.EnumKey(root, i)) as key:
                        if winreg.QueryValueEx(key, "DisplayName")[0] == "GNS3":
                            return winreg.QueryValueEx(key, "DisplayVersion")[0]
                except OSError:
                    continue
    return None


def gns3_running():
    out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq gns3.exe", "/NH"],
                         capture_output=True, text=True).stdout
    return "gns3.exe" in out.lower()


def library_zip(gns3_dir):
    return gns3_dir / "lib" / "library.zip"


def backup_zip(gns3_dir, version):
    return gns3_dir / "lib" / f"library.zip.mygns3theme-{version}.bak"


def is_patched(zip_path):
    with zipfile.ZipFile(zip_path) as z:
        return PATCH_MARKER in z.read("gns3/style.pyc")


def gui_ini(version):
    """Path of gns3_gui.ini for this GNS3 version (settings live in a major.minor folder)."""
    major_minor = ".".join(re.findall(r"\d+", version)[:2]) if version else None
    if major_minor and (GNS3_APPDATA / major_minor / "gns3_gui.ini").exists():
        return GNS3_APPDATA / major_minor / "gns3_gui.ini"
    candidates = sorted(GNS3_APPDATA.glob("*/gns3_gui.ini"))
    return candidates[-1] if candidates else None


def set_gui_style(version, style):
    ini = gui_ini(version)
    if not ini:
        info("gns3_gui.ini not found: start GNS3 once, then pick the style in Edit > Preferences > General")
        return
    if gns3_running():
        info(f"GNS3 is running: pick '{style}' in Edit > Preferences > General > Interface style")
        return
    settings = json.loads(ini.read_text(encoding="utf-8"))
    settings.setdefault("MainWindow", {})["style"] = style
    ini.write_text(json.dumps(settings, indent=4), encoding="utf-8")
    info(f"Interface style set to '{style}' in {ini}")


# --- bytecode ---

def fetch_source(version, module):
    path = CACHE_DIR / f"v{version}" / f"{module}.py"
    if not path.exists():
        url = SOURCE_URL.format(version=version, module=module)
        info(f"Downloading {url}")
        with urllib.request.urlopen(url, timeout=30) as resp:
            data = resp.read()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return path.read_text(encoding="utf-8")


def compile_like(source, original):
    """Compile source with the optimize level that reproduces the original code object.

    Returns the optimize level, or None if no level matches (sources differ from the build).
    """
    for optimize in (0, 1, 2):
        code = compile(source, original.co_filename, "exec", dont_inherit=True, optimize=optimize)
        if code == original:
            return optimize
    return None


def patch_settings(source):
    new, count = re.subn(r'^(STYLES = \[)', rf'\1"{STYLE_NAME}", ', source, flags=re.MULTILINE)
    if count != 1:
        fail("settings.py: STYLES list not found")
    return new


def patch_main_window(source):
    anchor = '        if style_name.startswith("Charcoal"):\n'
    if source.count(anchor) != 1:
        fail("main_window.py: style dispatch not found")
    replacement = (f'        if style_name == "{STYLE_NAME}":\n'
                   f'            style.setVioletStyle()\n'
                   f'        elif style_name.startswith("Charcoal"):\n')
    return source.replace(anchor, replacement)


def patch_style(source):
    # the method is appended to the file, so class Style must be its last top-level block
    tail = source.split("\nclass Style:", 1)
    if len(tail) != 2 or re.search(r"^\S", tail[1], flags=re.MULTILINE):
        fail("style.py: unexpected layout, class Style is not the last top-level block")
    return source.rstrip("\n") + "\n" + STYLE_PATCH.read_text(encoding="utf-8")


PATCHERS = {"settings": patch_settings, "main_window": patch_main_window, "style": patch_style}


def build_patched_modules(base_zip, version):
    """Return {zip entry name: new .pyc bytes} for every patched module."""
    replacements = {}
    with zipfile.ZipFile(base_zip) as z:
        for module in MODULES:
            entry = f"gns3/{module}.pyc"
            pyc = z.read(entry)
            if pyc[:4] != importlib.util.MAGIC_NUMBER:
                fail(f"{entry} was not built by Python {sys.version_info.major}.{sys.version_info.minor}: "
                     f"run this tool with the Python version GNS3 uses (py -3.13 for GNS3 3.1)")
            header, original = pyc[:16], marshal.loads(pyc[16:])
            source = fetch_source(version, module)
            optimize = compile_like(source, original)
            if optimize is None:
                fail(f"gns3-gui v{version} {module}.py does not match the installed {entry}; "
                     f"refusing to patch")
            patched = PATCHERS[module](source)
            code = compile(patched, original.co_filename, "exec", dont_inherit=True, optimize=optimize)
            replacements[entry] = header + marshal.dumps(code)
            info(f"{entry}: source verified, patched")
    return replacements


def rewrite_zip(src, dst, replacements):
    with zipfile.ZipFile(src) as zin, zipfile.ZipFile(dst, "w") as zout:
        zout.comment = zin.comment
        for item in zin.infolist():
            data = replacements.get(item.filename)
            zout.writestr(item, data if data is not None else zin.read(item.filename))


# --- commands ---

def resolve(args):
    version = args.gns3_version or installed_version()
    if not version:
        fail("GNS3 installation not found (pass --gns3-version)")
    gns3_dir = Path(args.gns3_dir)
    if not library_zip(gns3_dir).exists():
        fail(f"{library_zip(gns3_dir)} not found (pass --gns3-dir)")
    return gns3_dir, version


def cmd_patch(args):
    gns3_dir, version = resolve(args)
    if gns3_running():
        fail("close GNS3 before patching")
    lib, backup = library_zip(gns3_dir), backup_zip(gns3_dir, version)
    if not backup.exists():
        if is_patched(lib):
            fail(f"{lib} is already patched but its backup is missing; reinstall GNS3 to get a clean copy")
        shutil.copy2(lib, backup)
        info(f"Backup: {backup}")
    replacements = build_patched_modules(backup, version)
    tmp = lib.with_name("library.zip.mygns3theme-tmp")
    rewrite_zip(backup, tmp, replacements)
    os.replace(tmp, lib)
    info(f"GNS3 {version} patched: '{STYLE_NAME}' style added")


def cmd_unpatch(args):
    gns3_dir, version = resolve(args)
    if gns3_running():
        fail("close GNS3 before restoring")
    lib, backup = library_zip(gns3_dir), backup_zip(gns3_dir, version)
    if not backup.exists():
        if is_patched(lib):
            fail(f"no backup for GNS3 {version}; reinstall GNS3 to restore it")
        info("GNS3 is not patched, nothing to restore")
        return
    tmp = lib.with_name("library.zip.mygns3theme-tmp")
    shutil.copy2(backup, tmp)
    os.replace(tmp, lib)
    backup.unlink()
    info(f"Original library.zip restored for GNS3 {version}")


def cmd_apply(args):
    palette_path = Path(args.palette) if args.palette else THEME_SRC / "palette.json"
    values = json.loads(palette_path.read_text(encoding="utf-8"))
    values["theme_dir"] = THEME_DIR.as_posix()

    def render(text):
        def token(m):
            if m.group(1) not in values:
                fail(f"unknown token @{m.group(1)}@ (missing from {palette_path.name})")
            return str(values[m.group(1)])
        return re.sub(r"@([a-z_]+)@", token, text)

    (THEME_DIR / "assets").mkdir(parents=True, exist_ok=True)
    (THEME_DIR / "violet.qss").write_text(render((THEME_SRC / "violet.qss").read_text(encoding="utf-8")), encoding="utf-8")
    for svg in (THEME_SRC / "assets").glob("*.svg"):
        (THEME_DIR / "assets" / svg.name).write_text(render(svg.read_text(encoding="utf-8")), encoding="utf-8")
    shutil.copy2(palette_path, THEME_DIR / "palette.json")
    info(f"Theme written to {THEME_DIR}")
    if not args.no_select:
        set_gui_style(args.gns3_version or installed_version(), STYLE_NAME)


def cmd_reset_style(args):
    set_gui_style(args.gns3_version or installed_version(), "Classic")


def cmd_status(args):
    version = args.gns3_version or installed_version()
    lib = library_zip(Path(args.gns3_dir))
    print(f"GNS3 version : {version or 'not found'}")
    print(f"library.zip  : {lib} ({'patched' if lib.exists() and is_patched(lib) else 'original'})")
    if version:
        backup = backup_zip(Path(args.gns3_dir), version)
        print(f"backup       : {backup if backup.exists() else 'none'}")
    print(f"theme files  : {THEME_DIR} ({'present' if (THEME_DIR / 'violet.qss').exists() else 'missing'})")
    ini = gui_ini(version)
    if ini:
        style = json.loads(ini.read_text(encoding="utf-8")).get("MainWindow", {}).get("style")
        print(f"GUI style    : {style} ({ini})")


def main():
    parser = argparse.ArgumentParser(prog="mygns3theme", description="Violet Material 3 style for the GNS3 GUI (Windows)")
    parser.add_argument("--gns3-dir", default=str(DEFAULT_GNS3_DIR), help="GNS3 install folder")
    parser.add_argument("--gns3-version", help="GNS3 version (read from the registry by default)")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("patch", help="add the Violet style to GNS3 (elevated)").set_defaults(func=cmd_patch)
    sub.add_parser("unpatch", help="restore the original GNS3 files (elevated)").set_defaults(func=cmd_unpatch)
    apply = sub.add_parser("apply", help="render the theme and select it")
    apply.add_argument("--palette", help="palette JSON file (default: theme/palette.json)")
    apply.add_argument("--no-select", action="store_true", help="do not change the GNS3 interface style")
    apply.set_defaults(func=cmd_apply)
    sub.add_parser("reset-style", help="switch GNS3 back to the Classic style").set_defaults(func=cmd_reset_style)
    sub.add_parser("status", help="show the installation state").set_defaults(func=cmd_status)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
