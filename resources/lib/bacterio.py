import sys
import xbmcgui
import xbmcplugin
import xbmcaddon

from urllib.parse import parse_qsl
from utils.notifications import error

HANDLE = int(sys.argv[1])

CATEGORIES = [
    "Movies",
    "TV Shows",
    "Settings",
]


def get_params():
    return dict(parse_qsl(sys.argv[2].lstrip("?")))


def show_home():
    for category in CATEGORIES:
        li = xbmcgui.ListItem(label=category)
        url = f"{sys.argv[0]}?category={category}"
        success = xbmcplugin.addDirectoryItem(HANDLE, url, li, isFolder=True)
        if not success:
            error("Error building home page")
    xbmcplugin.endOfDirectory(HANDLE)


def show_movies():
    error("Not implemented")


def show_tv_shows():
    error("Not implemented")


if __name__ == "__main__":
    params = get_params()
    category = params.get("category")

    if not category:
        show_home()
    elif category == "Movies":
        show_movies()
    elif category == "TV Shows":
        show_tv_shows()
    elif category == "Settings":
        xbmcaddon.Addon().openSettings()
