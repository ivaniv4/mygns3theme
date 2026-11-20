#!/usr/bin/env python3
"""
mygns3theme - Material 3 themes for the GNS3 desktop GUI (Windows, Linux, macOS).

Adapted from gns3theme (https://github.com/n3oxmind/gns3theme, MIT license).
GNS3 has no theme API, so three GUI modules (settings, main_window, style) are
patched to add one style per installed theme:

  - pip / distribution packages ship the gns3 package as .py sources, which are
    patched directly;
  - the Windows and macOS builds are frozen with cx_Freeze and ship .pyc files
    (loose or packed in library.zip). Those are rebuilt from the official
    gns3-gui sources of the installed version, after checking that the sources
    compile to exactly the bytecode GNS3 ships.

The original files are always backed up. Themes themselves are data: the style
sheet and palette of every theme are rendered into the GNS3 settings folder, so
changing or adding a theme never needs a new patch.

Compatible with Python 3.10+. Patching a frozen build needs the same Python
minor version as GNS3 ("detect" tells which one).
"""

import argparse
import glob
import importlib.util
import json
import marshal
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

__version__ = "2.0.0"

IS_WINDOWS = sys.platform.startswith("win")
IS_MACOS = sys.platform == "darwin"

MODULES = ("settings", "main_window", "style")
# names only present in a patched style module (setVioletStyle: mygns3theme 1.x)
MARKERS = ("setCustomTheme", "setVioletStyle")
SOURCE_URL = "https://raw.githubusercontent.com/GNS3/gns3-gui/v{version}/gns3/{module}.py"
MAGIC_TO_PYTHON = {3413: "3.8", 3425: "3.9", 3439: "3.10", 3495: "3.11", 3531: "3.12", 3571: "3.13"}

REPO_DIR = Path(__file__).resolve().parent
PATCH_DIR = REPO_DIR / "patches"
TEMPLATE_DIR = REPO_DIR / "template"
THEMES_DIR = REPO_DIR / "themes"

if IS_WINDOWS:
    FONTS = {"font_family": "Segoe UI", "font_size": "10pt", "mono_font_family": "Consolas"}
elif IS_MACOS:
    FONTS = {"font_family": "Helvetica Neue", "font_size": "13pt", "mono_font_family": "Menlo"}
else:
    FONTS = {"font_family": "Sans Serif", "font_size": "10pt", "mono_font_family": "Monospace"}


def info(msg):
    print(f"[mygns3theme] {msg}")


def fail(msg):
    print(f"[mygns3theme] ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


# --- GNS3 settings folder (same rules as gns3/local_config.py) ---

def config_base():
    if IS_WINDOWS:
        return Path(os.path.expandvars("%APPDATA%")) / "GNS3"
    if os.environ.get("XDG_CONFIG_HOME"):
        return Path(os.environ["XDG_CONFIG_HOME"]) / "GNS3"
    return Path.home() / ".config" / "GNS3"


THEME_HOME = config_base() / "mygns3theme"
GUI_CONF_NAME = "gns3_gui.ini" if IS_WINDOWS else "gns3_gui.conf"


def gui_conf(version=None):
    """Path of the GNS3 GUI settings file (one folder per major.minor version)."""
    base = config_base()
    if version:
        major_minor = ".".join(re.findall(r"\d+", version)[:2])
        if (base / major_minor / GUI_CONF_NAME).exists():
            return base / major_minor / GUI_CONF_NAME

    def version_key(path):
        return [int(n) for n in re.findall(r"\d+", path.parent.name)]

    candidates = sorted(base.glob(f"*/{GUI_CONF_NAME}"), key=version_key)
    return candidates[-1] if candidates else None


def gns3_running():
    if IS_WINDOWS:
        out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq gns3.exe", "/NH"],
                             capture_output=True, text=True).stdout
        return "gns3.exe" in out.lower()
    try:
        return subprocess.run(["pgrep", "-x", "gns3"], capture_output=True).returncode == 0
    except FileNotFoundError:
        return False


# --- GNS3 installation ---

class Target:
    """The gns3 package of a GNS3 GUI install.

    kind is "zip" (path is library.zip), "pyc" (path is a folder of .pyc files)
    or "source" (path is a folder of .py files). app is the macOS bundle to
    re-sign after a change, if any.
    """

    def __init__(self, kind, path, app=None):
        self.kind = kind
        self.path = Path(path)
        self.app = app

    @property
    def ext(self):
        return ".py" if self.kind == "source" else ".pyc"

    def file(self, module):
        return self.path / f"{module}{self.ext}"

    def backup(self, module=None):
        if self.kind == "zip":
            backup = self.path.with_name(self.path.name + ".mygns3theme.bak")
            legacy = sorted(self.path.parent.glob(self.path.name + ".mygns3theme-*.bak"))
            if not backup.exists() and legacy:
                return legacy[-1]  # made by mygns3theme 1.x
            return backup
        return self.file(module).with_name(self.file(module).name + ".mygns3theme.bak")

    def read(self, module, original=False):
        if self.kind == "zip":
            with zipfile.ZipFile(self.backup() if original else self.path) as z:
                return z.read(f"gns3/{module}.pyc")
        return (self.backup(module) if original else self.file(module)).read_bytes()

    def is_patched(self):
        style = self.read("style")
        return any(marker.encode() in style for marker in MARKERS)

    def has_backup(self):
        if self.kind == "zip":
            return self.backup().exists()
        return all(self.backup(m).exists() for m in MODULES)

    def save_backup(self):
        if self.kind == "zip":
            shutil.copy2(self.path, self.backup())
        else:
            for module in MODULES:
                shutil.copy2(self.file(module), self.backup(module))

    def writable(self):
        # os.access ignores Windows ACLs, so actually try to create a file
        folder = self.path.parent if self.kind == "zip" else self.path
        try:
            with tempfile.TemporaryFile(dir=folder):
                pass
        except OSError:
            return False
        return os.access(self.path, os.W_OK)

    def version(self):
        data = self.read("version").decode("utf-8", "replace") if self.kind == "source" else None
        if data is not None:
            match = re.search(r'^__version__\s*=\s*["\']([^"\']+)["\']', data, flags=re.MULTILINE)
        else:
            match = re.search(rb"(\d+\.\d+\.\d+(?:[a-z]+\d*)?)", self.read("version"))
        if not match:
            return None
        value = match.group(1)
        return value.decode() if isinstance(value, bytes) else value

    def python_version(self):
        """Python minor version that built the frozen modules (None for sources)."""
        if self.kind == "source":
            return None
        magic = int.from_bytes(self.read("settings")[:2], "little")
        return MAGIC_TO_PYTHON.get(magic, f"unknown (magic {magic})")

    def python_matches(self):
        return self.kind == "source" or self.read("settings")[:4] == importlib.util.MAGIC_NUMBER

    def _clear_bytecode_cache(self, module):
        for cached in (self.path / "__pycache__").glob(f"{module}.*.pyc"):
            try:
                cached.unlink()
            except OSError:
                pass

    def write(self, modules):
        """Write {module: new content}, starting from the original files."""
        if self.kind == "zip":
            tmp = self.path.with_name(self.path.name + ".mygns3theme-tmp")
            rewrite_zip(self.backup(), tmp, {f"gns3/{m}.pyc": data for m, data in modules.items()})
            os.replace(tmp, self.path)
            return
        for module, data in modules.items():
            tmp = self.file(module).with_name(self.file(module).name + ".mygns3theme-tmp")
            tmp.write_bytes(data)
            shutil.copymode(self.file(module), tmp)
            os.replace(tmp, self.file(module))
            self._clear_bytecode_cache(module)

    def restore(self):
        if self.kind == "zip":
            tmp = self.path.with_name(self.path.name + ".mygns3theme-tmp")
            shutil.copy2(self.backup(), tmp)
            os.replace(tmp, self.path)
            self.backup().unlink()
            return
        for module in MODULES:
            os.replace(self.backup(module), self.file(module))
            self._clear_bytecode_cache(module)

    def launcher(self):
        """What starts this GNS3 install."""
        if self.app:
            return str(self.app)
        if self.kind == "zip" and IS_WINDOWS:
            return str(self.path.parent.parent / "gns3.exe")
        return shutil.which("gns3")


def rewrite_zip(src, dst, replacements):
    with zipfile.ZipFile(src) as zin, zipfile.ZipFile(dst, "w") as zout:
        zout.comment = zin.comment
        for item in zin.infolist():
            data = replacements.get(item.filename)
            zout.writestr(item, data if data is not None else zin.read(item.filename))


def target_from(path):
    """Find the gns3 package in a folder, a library.zip, or a macOS .app bundle."""
    path = Path(path).expanduser()
    app = next((p for p in (path, *path.parents) if p.suffix == ".app"), None)
    if path.is_file():
        if path.name.startswith("library") and path.suffix == ".zip":
            with zipfile.ZipFile(path) as z:
                if "gns3/main_window.pyc" in z.namelist():
                    return Target("zip", path, app)
        return None
    if not path.is_dir():
        return None
    for pkg in [path, path / "gns3", path / "lib" / "gns3"] + sorted(path.glob("**/gns3")):
        if pkg.name != "gns3" or not pkg.is_dir():
            continue
        if (pkg / "main_window.py").exists() and (pkg / "style.py").exists():
            return Target("source", pkg, app)
        if (pkg / "main_window.pyc").exists() and (pkg / "style.pyc").exists():
            return Target("pyc", pkg, app)
    for library in sorted(path.glob("**/library.zip")):
        target = target_from(library)
        if target:
            return target
    return None


def python_package_dirs():
    """Likely locations of a pip / distribution install of the gns3 package."""
    interpreters = []
    launcher = shutil.which("gns3")
    if launcher:
        try:
            with open(launcher, "rb") as f:
                first_line = f.readline(512).decode("utf-8", "replace").strip()
            if first_line.startswith("#!"):
                parts = first_line[2:].split()
                interpreters.append(parts[1:2] if parts and parts[0].endswith("/env") else parts[:1])
        except OSError:
            pass
    interpreters += [[sys.executable], ["python3"]]

    dirs = []
    probe = ("import importlib.util as u; s = u.find_spec('gns3'); "
             "print(s.submodule_search_locations[0] if s and s.submodule_search_locations else '')")
    for cmd in interpreters:
        if not cmd:
            continue
        try:
            out = subprocess.run(cmd + ["-c", probe], capture_output=True, text=True, timeout=30).stdout.strip()
        except (OSError, subprocess.TimeoutExpired):
            continue
        if out:
            dirs.append(Path(out))

    home = str(Path.home())
    for pattern in ("/usr/lib/python3*/site-packages/gns3", "/usr/lib/python3/dist-packages/gns3",
                    "/usr/lib64/python3*/site-packages/gns3", "/usr/local/lib/python3*/*-packages/gns3",
                    "/opt/homebrew/lib/python3*/site-packages/gns3",
                    home + "/.local/lib/python3*/site-packages/gns3",
                    home + "/.local/share/pipx/venvs/gns3-gui/lib/python3*/site-packages/gns3",
                    home + "/.local/pipx/venvs/gns3-gui/lib/python3*/site-packages/gns3"):
        dirs.extend(Path(p) for p in sorted(glob.glob(pattern)))
    return dirs


def find_target(gns3_dir=None):
    if gns3_dir:
        return target_from(gns3_dir)
    candidates = []
    if IS_WINDOWS:
        for env in ("ProgramW6432", "ProgramFiles"):
            if os.environ.get(env):
                candidates.append(Path(os.environ[env]) / "GNS3")
    if IS_MACOS:
        candidates += [Path("/Applications/GNS3.app"), Path.home() / "Applications" / "GNS3.app"]
    candidates += python_package_dirs()
    for candidate in candidates:
        if candidate.exists():
            target = target_from(candidate)
            if target:
                return target
    return None


def require_target(args):
    target = find_target(args.gns3_dir)
    if not target:
        fail("GNS3 GUI installation not found (pass --gns3-dir)")
    return target


# --- patches ---

def fetch_source(version, module):
    path = Path(tempfile.gettempdir()) / "mygns3theme-cache" / f"v{version}" / f"{module}.py"
    if not path.exists():
        url = SOURCE_URL.format(version=version, module=module)
        info(f"Downloading {url}")
        with urllib.request.urlopen(url, timeout=30) as resp:
            data = resp.read()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return path.read_text(encoding="utf-8")


def patch_settings(source):
    for module in ("os", "sys"):
        if not re.search(rf"^import {module}$", source, flags=re.MULTILINE):
            fail(f"settings.py: 'import {module}' not found")
    snippet = (PATCH_DIR / "settings_patch.py").read_text(encoding="utf-8")
    new, count = re.subn(r"^STYLES = \[",
                         lambda m: snippet + "STYLES = list(mygns3theme_themes()) + [",
                         source, flags=re.MULTILINE)
    if count != 1:
        fail("settings.py: STYLES list not found")
    return new


def patch_main_window(source):
    anchor = '        if style_name.startswith("Charcoal"):\n'
    if source.count(anchor) != 1:
        fail("main_window.py: style dispatch not found")
    replacement = ('        if style.hasCustomTheme(style_name):\n'
                   '            style.setCustomTheme(style_name)\n'
                   '        elif style_name.startswith("Charcoal"):\n')
    return source.replace(anchor, replacement)


def patch_style(source):
    # the methods are appended to the file, so class Style must be its last top-level block
    parts = source.split("\nclass Style:", 1)
    if len(parts) != 2 or re.search(r"^\S", parts[1], flags=re.MULTILINE):
        fail("style.py: unexpected layout, class Style is not the last top-level block")
    return source.rstrip("\n") + "\n" + (PATCH_DIR / "style_patch.py").read_text(encoding="utf-8")


PATCHERS = {"settings": patch_settings, "main_window": patch_main_window, "style": patch_style}


def compile_like(source, original):
    """Optimize level that reproduces the original code object, or None if the sources differ."""
    for optimize in (0, 1, 2):
        code = compile(source, original.co_filename, "exec", dont_inherit=True, optimize=optimize)
        if code == original:
            return optimize
    return None


def build_module(target, module, original, version):
    if target.kind == "source":
        return PATCHERS[module](original.decode("utf-8")).encode("utf-8")
    header, code = original[:16], marshal.loads(original[16:])
    source = fetch_source(version, module)
    optimize = compile_like(source, code)
    if optimize is None:
        fail(f"gns3-gui v{version} {module}.py does not match the installed {module}.pyc; refusing to patch")
    patched = compile(PATCHERS[module](source), code.co_filename, "exec", dont_inherit=True, optimize=optimize)
    return header + marshal.dumps(patched)


def resign(target):
    """A modified macOS bundle must be signed again or Gatekeeper refuses to start it."""
    if not (IS_MACOS and target.app):
        return
    result = subprocess.run(["codesign", "--force", "--deep", "--sign", "-", str(target.app)],
                            capture_output=True, text=True)
    if result.returncode == 0:
        info(f"Re-signed {target.app} (ad-hoc)")
    else:
        info(f"WARNING: could not re-sign {target.app}: {result.stderr.strip()}")


# --- themes ---

def mix(color_a, color_b, amount):
    """Blend two #RRGGBB colors (amount = share of color_b)."""
    a = [int(color_a[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(color_b[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * amount):02X}" for x, y in zip(a, b))


def load_themes():
    """Every theme of themes/, light ones first, as (id, data) pairs."""
    themes = []
    for path in THEMES_DIR.glob("*.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        themes.append((path.stem, data))
    themes.sort(key=lambda item: (item[1].get("mode") != "light", item[1]["name"].lower()))
    return themes


def find_theme(themes, wanted):
    for theme_id, data in themes:
        if wanted.lower() in (theme_id.lower(), data["name"].lower()):
            return theme_id, data
    fail(f"unknown theme '{wanted}' (see: mygns3theme.py list)")


def theme_values(data, theme_dir):
    """Template values of a theme: its Material 3 colors plus the derived ones."""
    c = data["colors"]
    light = data.get("mode", "light") == "light"
    canvas = c["surface_container_lowest"] if light else c["surface"]
    values = dict(c)
    values.update(FONTS)
    values.update({
        "mode": data.get("mode", "light"),
        "primary_hover": mix(c["primary"], c["on_primary"], 0.08),
        "primary_pressed": mix(c["primary"], c["on_primary"], 0.16),
        "secondary_container_hover": mix(c["secondary_container"], c["on_secondary_container"], 0.08),
        "secondary_container_pressed": mix(c["secondary_container"], c["on_secondary_container"], 0.16),
        "disabled_text": mix(c["surface"], c["on_surface"], 0.38),
        "canvas": canvas,
        "drawing_grid": mix(canvas, c["outline_variant"], 0.3),
        "node_grid": mix(canvas, c["outline_variant"], 0.6),
        "tint_icons": True,
        "icon": c["primary"],
        "icon_active": c["on_primary_container"],
        "theme_dir": Path(theme_dir).as_posix(),
    })
    values.update(data.get("overrides", {}))
    return values


def render(text, values, where):
    def token(match):
        if match.group(1) not in values:
            fail(f"{where}: unknown token @{match.group(1)}@")
        return str(values[match.group(1)])
    return re.sub(r"@([a-z_]+)@", token, text)


def render_themes(dest):
    """Render every theme into dest/<id>/ and write the dest/themes.json index."""
    dest = Path(dest)
    template = (TEMPLATE_DIR / "style.qss").read_text(encoding="utf-8")
    index = {}
    for theme_id, data in load_themes():
        theme_dir = dest / theme_id
        if theme_dir.exists():
            shutil.rmtree(theme_dir)
        (theme_dir / "assets").mkdir(parents=True)
        values = theme_values(data, theme_dir)
        (theme_dir / "style.qss").write_text(render(template, values, "style.qss"), encoding="utf-8")
        for svg in (TEMPLATE_DIR / "assets").glob("*.svg"):
            (theme_dir / "assets" / svg.name).write_text(
                render(svg.read_text(encoding="utf-8"), values, svg.name), encoding="utf-8")
        palette = {k: v for k, v in values.items() if k != "theme_dir"}
        (theme_dir / "palette.json").write_text(json.dumps(palette, indent=4), encoding="utf-8")
        index[data["name"]] = theme_id
    (dest / "themes.json").write_text(json.dumps(index, indent=4), encoding="utf-8")
    return index


def set_gui_style(style, version=None):
    conf = gui_conf(version)
    if not conf:
        info("GNS3 settings not found: start GNS3 once, then pick the theme in "
             "Edit > Preferences > General > Interface style")
        return
    if gns3_running():
        info(f"GNS3 is running: pick '{style}' in Edit > Preferences > General > Interface style")
        return
    settings = json.loads(conf.read_text(encoding="utf-8"))
    settings.setdefault("MainWindow", {})["style"] = style
    conf.write_text(json.dumps(settings, indent=4), encoding="utf-8")
    info(f"Interface style set to '{style}' in {conf}")


def current_style(version=None):
    conf = gui_conf(version)
    if not conf:
        return None
    return json.loads(conf.read_text(encoding="utf-8")).get("MainWindow", {}).get("style")


# --- commands ---

def cmd_detect(args):
    target = find_target(args.gns3_dir)
    result = None
    if target:
        result = {
            "kind": target.kind,
            "path": str(target.path),
            "app": str(target.app) if target.app else None,
            "version": target.version(),
            "python": target.python_version(),
            "python_ok": target.python_matches(),
            "writable": target.writable(),
            "patched": target.is_patched(),
            "running": gns3_running(),
            "launcher": target.launcher(),
        }
    if args.json:
        print(json.dumps(result))
    elif result:
        for key, value in result.items():
            print(f"{key:10}: {value}")
    if not result:
        fail("GNS3 GUI installation not found (pass --gns3-dir)")


def cmd_patch(args):
    target = require_target(args)
    if gns3_running():
        fail("close GNS3 before patching")
    if not target.python_matches():
        fail(f"this GNS3 build needs Python {target.python_version()} to be patched "
             f"(running {sys.version_info.major}.{sys.version_info.minor})")
    if target.is_patched():
        if not target.has_backup():
            fail(f"{target.path} is already patched but its backup is missing; reinstall GNS3")
    else:
        target.save_backup()
        info(f"Backup of the original files saved next to {target.path}")
    version = target.version()
    modules = {}
    for module in MODULES:
        modules[module] = build_module(target, module, target.read(module, original=True), version)
        info(f"{module}: patched")
    target.write(modules)
    resign(target)
    info(f"GNS3 {version} ({target.kind} install at {target.path}) patched")


def cmd_unpatch(args):
    target = require_target(args)
    if gns3_running():
        fail("close GNS3 before restoring")
    if not target.is_patched():
        info("GNS3 is not patched, nothing to restore")
        return
    if not target.has_backup():
        fail("backup not found; reinstall GNS3 to restore it")
    target.restore()
    resign(target)
    info(f"Original GNS3 files restored at {target.path}")


def cmd_apply(args):
    for legacy in ("violet.qss", "palette.json", "assets"):  # left by mygns3theme 1.x
        path = THEME_HOME / legacy
        if path.is_dir():
            shutil.rmtree(path)
        elif path.exists():
            path.unlink()
    index = render_themes(THEME_HOME)
    info(f"{len(index)} themes written to {THEME_HOME}")
    if args.no_select:
        return
    themes = load_themes()
    if args.theme:
        name = find_theme(themes, args.theme)[1]["name"]
    else:
        style = current_style()
        name = style if style in index else themes[0][1]["name"]
    target = find_target(args.gns3_dir)
    set_gui_style(name, target.version() if target else None)


def cmd_list(args):
    themes = load_themes()
    if args.json:
        print(json.dumps([{"id": i, "name": d["name"], "mode": d.get("mode", "light")} for i, d in themes]))
        return
    for theme_id, data in themes:
        print(f"{theme_id:18} {data['name']:22} {data.get('mode', 'light')}")


def cmd_select(args):
    name = find_theme(load_themes(), args.theme)[1]["name"]
    if not (THEME_HOME / "themes.json").exists():
        render_themes(THEME_HOME)
    target = find_target(args.gns3_dir)
    set_gui_style(name, target.version() if target else None)


def cmd_reset_style(args):
    target = find_target(args.gns3_dir)
    set_gui_style("Classic", target.version() if target else None)


def cmd_remove_themes(args):
    if THEME_HOME.exists():
        shutil.rmtree(THEME_HOME)
        info(f"Removed {THEME_HOME}")


def cmd_status(args):
    target = find_target(args.gns3_dir)
    if target:
        print(f"GNS3        : {target.version()} ({target.kind} install)")
        print(f"location    : {target.path}")
        print(f"state       : {'patched' if target.is_patched() else 'original'}")
        print(f"python      : {target.python_version() or 'any Python 3.10+'}")
    else:
        print("GNS3        : not found")
    installed = (THEME_HOME / "themes.json").exists()
    print(f"themes      : {THEME_HOME} ({'installed' if installed else 'not installed'})")
    conf = gui_conf(target.version() if target else None)
    if conf:
        print(f"GUI style   : {current_style(target.version() if target else None)} ({conf})")


def cmd_selftest(args):
    """Checks used by CI: themes render, patches apply to the official sources and compile."""
    with tempfile.TemporaryDirectory() as tmp:
        index = render_themes(tmp)
        for theme_id in index.values():
            palette = json.loads((Path(tmp) / theme_id / "palette.json").read_text(encoding="utf-8"))
            for key, value in palette.items():
                if isinstance(value, str) and value.startswith("#") and not re.fullmatch(r"#[0-9A-Fa-f]{6}", value):
                    fail(f"{theme_id}: invalid color {key}={value}")
        info(f"{len(index)} themes render correctly")
    for version in args.gns3_version or ["3.1.0a7"]:
        for module in MODULES:
            compile(PATCHERS[module](fetch_source(version, module)), f"gns3/{module}.py", "exec")
        info(f"patches apply and compile on gns3-gui v{version}")


def main():
    parser = argparse.ArgumentParser(prog="mygns3theme",
                                     description="Material 3 themes for the GNS3 desktop GUI")
    parser.add_argument("--version", action="version", version=f"mygns3theme {__version__}")
    parser.add_argument("--gns3-dir", help="GNS3 install folder, library.zip, .app bundle or gns3 package folder")
    sub = parser.add_subparsers(dest="command", required=True)

    detect = sub.add_parser("detect", help="describe the GNS3 installation")
    detect.add_argument("--json", action="store_true")
    detect.set_defaults(func=cmd_detect)
    sub.add_parser("patch", help="add theme support to GNS3 (may need admin/root)").set_defaults(func=cmd_patch)
    sub.add_parser("unpatch", help="restore the original GNS3 files (may need admin/root)").set_defaults(func=cmd_unpatch)
    apply = sub.add_parser("apply", help="install the themes and select one")
    apply.add_argument("--theme", help="theme id or name (default: keep the current one)")
    apply.add_argument("--no-select", action="store_true", help="do not change the GNS3 interface style")
    apply.set_defaults(func=cmd_apply)
    themes = sub.add_parser("list", help="list the available themes")
    themes.add_argument("--json", action="store_true")
    themes.set_defaults(func=cmd_list)
    select = sub.add_parser("select", help="select an installed theme")
    select.add_argument("theme", help="theme id or name")
    select.set_defaults(func=cmd_select)
    sub.add_parser("reset-style", help="switch GNS3 back to the Classic style").set_defaults(func=cmd_reset_style)
    sub.add_parser("remove-themes", help="delete the installed theme files").set_defaults(func=cmd_remove_themes)
    sub.add_parser("status", help="show the installation state").set_defaults(func=cmd_status)
    selftest = sub.add_parser("selftest", help="check themes and patches (no GNS3 needed)")
    selftest.add_argument("--gns3-version", action="append", help="gns3-gui version to test against")
    selftest.set_defaults(func=cmd_selftest)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
