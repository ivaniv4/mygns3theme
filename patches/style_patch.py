
    def hasCustomTheme(self, name):
        """
        Tells whether a style name is a theme installed by mygns3theme.
        """

        from gns3.settings import mygns3theme_themes
        return name in mygns3theme_themes()

    def setCustomTheme(self, name):
        """
        Sets a GUI style installed by mygns3theme (added by mygns3theme).

        The style sheet and colors are read from the theme folder written by
        "mygns3theme.py apply".
        """

        import json
        import os
        from gns3.settings import mygns3theme_dir, mygns3theme_themes

        theme_dir = os.path.join(mygns3theme_dir(), mygns3theme_themes().get(name, ""))
        style = ""
        style_file = QtCore.QFile(os.path.join(theme_dir, "style.qss"))
        if style_file.open(QtCore.QIODeviceBase.OpenModeFlag.ReadOnly):
            style = QtCore.QTextStream(style_file).readAll()
            style_file.close()
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

        def color(key, default):
            return QtGui.QColor(colors.get(key, default))

        # Fusion honours the whole palette, unlike the native Windows and macOS styles
        QtWidgets.QApplication.setStyle("Fusion")

        role = QtGui.QPalette.ColorRole
        palette = QtGui.QPalette()
        for color_role, value in ((role.Window, color("surface", "#FEF7FF")),
                                  (role.WindowText, color("on_surface", "#1D1B20")),
                                  (role.Base, color("surface_container_lowest", "#FFFFFF")),
                                  (role.AlternateBase, color("surface_container_low", "#F7F2FA")),
                                  (role.Text, color("on_surface", "#1D1B20")),
                                  (role.PlaceholderText, color("outline", "#79747E")),
                                  (role.Button, color("secondary_container", "#E8DEF8")),
                                  (role.ButtonText, color("on_secondary_container", "#1D192B")),
                                  (role.BrightText, color("on_primary", "#FFFFFF")),
                                  (role.Highlight, color("primary", "#6750A4")),
                                  (role.HighlightedText, color("on_primary", "#FFFFFF")),
                                  (role.ToolTipBase, color("inverse_surface", "#322F35")),
                                  (role.ToolTipText, color("inverse_on_surface", "#F5EFF7")),
                                  (role.Link, color("primary", "#6750A4")),
                                  (role.Light, color("surface_container_lowest", "#FFFFFF")),
                                  (role.Midlight, color("surface_container_high", "#ECE6F0")),
                                  (role.Mid, color("outline_variant", "#CAC4D0")),
                                  (role.Dark, color("outline", "#79747E")),
                                  (role.Shadow, color("on_surface_variant", "#49454F"))):
            palette.setColor(color_role, value)
        disabled_text = color("disabled_text", "#A49FA9")
        for color_role in (role.WindowText, role.Text, role.ButtonText):
            palette.setColor(QtGui.QPalette.ColorGroup.Disabled, color_role, disabled_text)
        QtGui.QGuiApplication.setPalette(palette)

        self._mw.setStyleSheet(style)

        graphics_view = self._mw.uiGraphicsView
        if hasattr(graphics_view, "resetGridColors"):
            graphics_view._drawing_grid_color = color("drawing_grid", "#F1ECF8")
            graphics_view._node_grid_color = color("node_grid", "#E4DAF3")
            graphics_view.viewport().update()
        self._mw.uiConsoleTextEdit.setDefaultTextColor(color("on_surface", "#1D1B20"))

        if dark:
            # same light grey as the built-in Dark style, so switching back resets it
            topology_view_settings = graphics_view.settings()
            for key in ("default_note_color", "default_label_color", "default_link_color"):
                if topology_view_settings[key] == "#000000":
                    topology_view_settings[key] = "#dfe1e2"
            graphics_view.setSettings(topology_view_settings)
            self._setCharcoalIcons()
        else:
            self._resetDefaultColors()
            self._setClassicIcons()
        if colors.get("tint_icons", True):
            self._tintActionIcons(color("icon", "#6750A4"), color("icon_active", "#4F378B"))

    def _tintActionIcons(self, normal_color, active_color):
        """
        Recolors the grey action icons with the theme colors, keeping their shading
        (added by mygns3theme).
        """

        def tint(pixmap, tint_color):
            image = pixmap.toImage().convertToFormat(QtGui.QImage.Format.Format_ARGB32_Premultiplied)
            tinted = QtGui.QImage(image)
            painter = QtGui.QPainter(tinted)
            # overlay keeps white and dark details, turns the greys into shades of the tint
            painter.setCompositionMode(QtGui.QPainter.CompositionMode.CompositionMode_Overlay)
            painter.fillRect(tinted.rect(), tint_color)
            # then restore the original transparency
            painter.setCompositionMode(QtGui.QPainter.CompositionMode.CompositionMode_DestinationIn)
            painter.drawImage(0, 0, image)
            painter.end()
            return QtGui.QPixmap.fromImage(tinted)

        size = QtCore.QSize(128, 128)
        mode, state = QtGui.QIcon.Mode, QtGui.QIcon.State
        for action in self._mw.findChildren(QtGui.QAction):
            icon = action.icon()
            if icon.isNull():
                continue
            tinted_icon = QtGui.QIcon()
            for icon_state in (state.Off, state.On):
                tinted_icon.addPixmap(tint(icon.pixmap(size, mode.Normal, icon_state), normal_color), mode.Normal, icon_state)
                tinted_icon.addPixmap(tint(icon.pixmap(size, mode.Active, icon_state), active_color), mode.Active, icon_state)
            action.setIcon(tinted_icon)
