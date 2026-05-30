import os
import sys
import xbmcaddon
import xbmcgui
import xbmcplugin

from utils.router import url

HANDLE = int(sys.argv[1])


def _icon(name: str) -> str:
    return os.path.join(xbmcaddon.Addon().getAddonInfo("path"), "resources", "media", "icons", name + ".png")


def show_home():
    _first_run_check()

    _item("Search", url("/search/"), icon="search")
    _item("Movies", url("/movies/"), icon="movies")
    _item("TV Shows", url("/shows/"), icon="tv")
    _item("Settings", url("/settings/"), icon="settings")
    xbmcplugin.endOfDirectory(HANDLE)


def _first_run_check():
    try:
        from services.real_debrid import RealDebrid
        from services.torbox import TorBox
        if RealDebrid.is_authenticated or TorBox.is_authenticated:
            return
        win = xbmcgui.Window(10000)
        if win.getProperty("bacterio.welcome_shown"):
            return
        win.setProperty("bacterio.welcome_shown", "1")
        go = xbmcgui.Dialog().yesno(
            "Welcome to Bacterio!",
            (
                "To stream movies and TV shows you need a debrid service.\n\n"
                "Supported: [B]TorBox[/B] (recommended) or [B]Real Debrid[/B].\n\n"
                "Open Settings now to connect your account?"
            ),
            nolabel="Later",
            yeslabel="Open Settings",
        )
        if go:
            xbmcaddon.Addon().openSettings()
    except Exception:
        pass


def _item(label: str, url: str, is_folder: bool = True, icon: str = "folder"):
    li = xbmcgui.ListItem(label=label)
    icon_path = _icon(icon)
    li.setArt({"icon": icon_path, "thumb": icon_path, "poster": icon_path})
    _ = xbmcplugin.addDirectoryItem(HANDLE, url, li, isFolder=is_folder)
