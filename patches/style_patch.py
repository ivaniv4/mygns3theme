
    def hasCustomTheme(self, name):
        """
        Tells whether a style name is a theme installed by mygns3theme.
        """

        from gns3.settings import mygns3theme_themes
        return name in mygns3theme_themes()

    @staticmethod
    def _qtEnum(cls, group, name):
        """
        Reads an enum member on both PyQt5 (cls.name) and PyQt6 (cls.group.name).
        """

        enum = getattr(cls, group, None)
        if enum is not None and hasattr(enum, name):
            return getattr(enum, name)
        return getattr(cls, name)

    def setCustomTheme(self, name):
        """
        Sets a GUI style installed by mygns3theme (added by mygns3theme).

        The style sheet and colors are read from the theme folder written by
        "mygns3theme.py apply". Works with PyQt5 and PyQt6.
        """

        import json
        import os
        from gns3.qt import QtCore, QtGui, QtWidgets  # older style modules do not import QtWidgets
        from gns3.settings import mygns3theme_dir, mygns3theme_themes

        theme_dir = os.path.join(mygns3theme_dir(), mygns3theme_themes().get(name, ""))
        try:
            with open(os.path.join(theme_dir, "style.qss"), encoding="utf-8") as f:
                style = f.read()
        except OSError:
            style = ""
        if not style:
            # the theme files are missing: fall back to the classic style
            self.setClassicStyle()
            return

        try:
            with open(os.path.join(theme_dir, "palette.json"), encoding="utf-8") as f:
                colors = json.load(f)
        except (OSError, ValueError):
            colors = {}
        dark = colors.get("mode") == "dark"

        # start from a built-in style: it resets the icons and, in newer versions, the default colors
        if dark:
            self.setCharcoalStyle()
        else:
            self.setClassicStyle()

        def color(key, default):
            return QtGui.QColor(colors.get(key, default))

        # Fusion honours the whole palette, unlike the native Windows and macOS styles
        QtWidgets.QApplication.setStyle("Fusion")

        enum = self._qtEnum
        role = lambda role_name: enum(QtGui.QPalette, "ColorRole", role_name)  # noqa: E731
        palette = QtGui.QPalette()
        for role_name, value in (("Window", color("surface", "#FEF7FF")),
                                 ("WindowText", color("on_surface", "#1D1B20")),
                                 ("Base", color("surface_container_lowest", "#FFFFFF")),
                                 ("AlternateBase", color("surface_container_low", "#F7F2FA")),
                                 ("Text", color("on_surface", "#1D1B20")),
                                 ("Button", color("secondary_container", "#E8DEF8")),
                                 ("ButtonText", color("on_secondary_container", "#1D192B")),
                                 ("BrightText", color("on_primary", "#FFFFFF")),
                                 ("Highlight", color("primary", "#6750A4")),
                                 ("HighlightedText", color("on_primary", "#FFFFFF")),
                                 ("ToolTipBase", color("inverse_surface", "#322F35")),
                                 ("ToolTipText", color("inverse_on_surface", "#F5EFF7")),
                                 ("Link", color("primary", "#6750A4")),
                                 ("Light", color("surface_container_lowest", "#FFFFFF")),
                                 ("Midlight", color("surface_container_high", "#ECE6F0")),
                                 ("Mid", color("outline_variant", "#CAC4D0")),
                                 ("Dark", color("outline", "#79747E")),
                                 ("Shadow", color("on_surface_variant", "#49454F"))):
            palette.setColor(role(role_name), value)
        if hasattr(QtGui.QPalette, "PlaceholderText") or hasattr(QtGui.QPalette.ColorRole, "PlaceholderText"):
            palette.setColor(role("PlaceholderText"), color("outline", "#79747E"))
        disabled = enum(QtGui.QPalette, "ColorGroup", "Disabled")
        for role_name in ("WindowText", "Text", "ButtonText"):
            palette.setColor(disabled, role(role_name), color("disabled_text", "#A49FA9"))
        QtGui.QGuiApplication.setPalette(palette)

        self._mw.setStyleSheet(style)

        graphics_view = getattr(self._mw, "uiGraphicsView", None)
        if graphics_view is not None and hasattr(graphics_view, "_drawing_grid_color"):
            # the grid colors only exist in recent GNS3 versions
            graphics_view._drawing_grid_color = color("drawing_grid", "#F1ECF8")
            graphics_view._node_grid_color = color("node_grid", "#E4DAF3")
            graphics_view.viewport().update()
        console = getattr(self._mw, "uiConsoleTextEdit", None)
        if console is not None and hasattr(console, "setDefaultTextColor"):
            console.setDefaultTextColor(color("on_surface", "#1D1B20"))

        if dark and graphics_view is not None and hasattr(graphics_view, "settings"):
            # same light grey as the built-in Dark style, so labels stay readable on a dark canvas
            topology_view_settings = graphics_view.settings()
            for key in ("default_note_color", "default_label_color", "default_link_color"):
                if topology_view_settings.get(key) == "#000000":
                    topology_view_settings[key] = "#dfe1e2"
            graphics_view.setSettings(topology_view_settings)

        if colors.get("tint_icons", True):
            self._tintActionIcons(color("icon", "#6750A4"), color("icon_active", "#4F378B"))

    def _tintActionIcons(self, normal_color, active_color):
        """
        Recolors the grey action icons with the theme colors, keeping their shading
        (added by mygns3theme).
        """

        from gns3.qt import QtCore, QtGui, QtWidgets

        enum = self._qtEnum
        image_format = enum(QtGui.QImage, "Format", "Format_ARGB32_Premultiplied")
        overlay = enum(QtGui.QPainter, "CompositionMode", "CompositionMode_Overlay")
        destination_in = enum(QtGui.QPainter, "CompositionMode", "CompositionMode_DestinationIn")
        mode_normal, mode_active = enum(QtGui.QIcon, "Mode", "Normal"), enum(QtGui.QIcon, "Mode", "Active")
        state_off, state_on = enum(QtGui.QIcon, "State", "Off"), enum(QtGui.QIcon, "State", "On")
        # QAction moved from QtWidgets (Qt5) to QtGui (Qt6)
        action_class = getattr(QtGui, "QAction", None) or QtWidgets.QAction

        def tint(pixmap, tint_color):
            image = pixmap.toImage().convertToFormat(image_format)
            tinted = QtGui.QImage(image)
            painter = QtGui.QPainter(tinted)
            # overlay keeps white and dark details, turns the greys into shades of the tint
            painter.setCompositionMode(overlay)
            painter.fillRect(tinted.rect(), tint_color)
            # then restore the original transparency
            painter.setCompositionMode(destination_in)
            painter.drawImage(0, 0, image)
            painter.end()
            return QtGui.QPixmap.fromImage(tinted)

        size = QtCore.QSize(128, 128)
        for action in self._mw.findChildren(action_class):
            icon = action.icon()
            if icon.isNull():
                continue
            tinted_icon = QtGui.QIcon()
            for icon_state in (state_off, state_on):
                tinted_icon.addPixmap(tint(icon.pixmap(size, mode_normal, icon_state), normal_color), mode_normal, icon_state)
                tinted_icon.addPixmap(tint(icon.pixmap(size, mode_active, icon_state), active_color), mode_active, icon_state)
            action.setIcon(tinted_icon)
