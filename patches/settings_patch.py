def mygns3theme_dir():
    """
    Folder of the themes installed by mygns3theme (added by mygns3theme).
    """

    if sys.platform.startswith("win"):
        base = os.path.join(os.path.expandvars("%APPDATA%"), "GNS3")
    elif os.environ.get("XDG_CONFIG_HOME"):
        base = os.path.join(os.environ["XDG_CONFIG_HOME"], "GNS3")
    else:
        base = os.path.join(os.path.expanduser("~"), ".config", "GNS3")
    return os.path.join(base, "mygns3theme")


def mygns3theme_themes():
    """
    Returns the {style name: theme folder} map of the themes installed by mygns3theme.
    """

    import json

    try:
        with open(os.path.join(mygns3theme_dir(), "themes.json"), encoding="utf-8") as f:
            themes = json.load(f)
    except (OSError, ValueError):
        return {}
    if not isinstance(themes, dict):
        return {}
    return {name: folder for name, folder in themes.items() if isinstance(name, str) and isinstance(folder, str)}


