#!/usr/bin/env python3
"""
Runs the patched GNS3 style module of several GNS3 versions against a fake main
window, with a real PyQt5 or PyQt6, and checks that every theme applies.

The official gns3-gui sources are downloaded for each version, patched exactly
like the installers do, then setCustomTheme() is executed headless.

Usage: python tests/qt_styles.py 5|6 [gns3-version ...]
"""

import importlib
import json
import os
import sys
import tempfile
import types
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import mygns3theme  # noqa: E402

DEFAULT_VERSIONS = {
    "5": ["2.0.0", "2.1.21", "2.2.30", "2.2.50", "3.0.0", "3.0.5"],
    "6": ["2.2.61", "3.0.6", "3.1.0a7"],
}


class Canvas:
    """Stands for the topology view; the grid colors only exist in recent GNS3 versions."""

    def __init__(self, with_grid):
        self._settings = {"default_note_color": "#000000", "default_label_color": "#000000",
                          "default_link_color": "#000000"}
        if with_grid:
            self._drawing_grid_color = self._node_grid_color = None

    def settings(self):
        return dict(self._settings)

    def setSettings(self, settings):
        self._settings = settings

    def viewport(self):
        return types.SimpleNamespace(update=lambda: None)

    def resetGridColors(self):
        pass


class Console:
    def setDefaultTextColor(self, color):
        self.color = color


def make_window_class(QtCore, QtGui, QtWidgets):
    action_class = getattr(QtGui, "QAction", None) or QtWidgets.QAction

    class Window(QtWidgets.QMainWindow):
        """Every uiXxxAction the style code asks for is created on demand."""

        def __init__(self, modern):
            super().__init__()
            self.uiGraphicsView = Canvas(modern)
            if modern:
                self.uiConsoleTextEdit = Console()
            self._pixmap = QtGui.QPixmap(32, 32)
            self._pixmap.fill(QtGui.QColor("#888888"))
            self.probe = action_class("probe", self)
            self.probe.setIcon(QtGui.QIcon(self._pixmap))

        def __getattr__(self, name):
            if name.startswith("ui") and name.endswith("Action"):
                action = action_class(name, self)
                action.setIcon(QtGui.QIcon(self._pixmap))
                object.__setattr__(self, name, action)
                return action
            raise AttributeError(name)

    return Window


def main():
    qt = sys.argv[1] if len(sys.argv) > 1 else ""
    if qt not in DEFAULT_VERSIONS:
        sys.exit(__doc__)
    versions = sys.argv[2:] or DEFAULT_VERSIONS[qt]
    QtCore, QtGui, QtWidgets = (importlib.import_module(f"PyQt{qt}.{name}")
                                for name in ("QtCore", "QtGui", "QtWidgets"))
    app = QtWidgets.QApplication([])  # noqa: F841 (must stay alive)
    Window = make_window_class(QtCore, QtGui, QtWidgets)

    home = tempfile.mkdtemp()
    index = mygns3theme.render_themes(home)

    # fake gns3 package: what the patched style module imports
    gns3 = types.ModuleType("gns3")
    gns3.__path__ = []
    gns3_qt = types.ModuleType("gns3.qt")
    gns3_qt.QtCore, gns3_qt.QtGui, gns3_qt.QtWidgets = QtCore, QtGui, QtWidgets
    gns3_settings = types.ModuleType("gns3.settings")
    gns3_settings.mygns3theme_dir = lambda: home
    gns3_settings.mygns3theme_themes = lambda: json.loads(Path(home, "themes.json").read_text())
    sys.modules.update({"gns3": gns3, "gns3.qt": gns3_qt, "gns3.settings": gns3_settings})

    failures = 0
    for version in versions:
        source = mygns3theme.fetch_source(version, "style")
        module = types.ModuleType("gns3.style")
        exec(compile(mygns3theme.patch_style(source), "style.py", "exec"), module.__dict__)
        modern = "_resetDefaultColors" in source
        for name in index:
            try:
                window = Window(modern)
                style = module.Style(window)
                assert style.hasCustomTheme(name)
                style.setCustomTheme(name)
                assert "QPushButton" in window.styleSheet(), "style sheet not applied"
                tinted = window.probe.icon().pixmap(QtCore.QSize(32, 32)).toImage().pixelColor(16, 16).name()
                assert tinted != "#888888", "icons were not tinted"
            except Exception as error:  # report every failure, not only the first
                failures += 1
                print(f"FAIL Qt{qt} gns3 {version:8} {name}: {type(error).__name__}: {error}")
        print(f"ok   Qt{qt} gns3 {version:8} {len(index)} themes")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
