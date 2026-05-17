import sys
import xbmcgui
import xbmcplugin

HANDLE = int(sys.argv[1])
_BASE = sys.argv[0]

_CATEGORIES = [
    ("Movies", "movies"),
    ("TV Shows", "shows"),
    ("Settings", "settings"),
]


def show_home():
    for label, key in _CATEGORIES:
        li = xbmcgui.ListItem(label=label)
        url = f"{_BASE}?category={key}"
        xbmcplugin.addDirectoryItem(HANDLE, url, li, isFolder=True)
    xbmcplugin.endOfDirectory(HANDLE)
