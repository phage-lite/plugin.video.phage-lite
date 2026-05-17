import sys
import xbmcgui
import xbmcplugin

HANDLE = int(sys.argv[1])
_BASE = sys.argv[0]


def show_home():
    _item("Search", f"{_BASE}?action=search")
    _item("Movies", f"{_BASE}?category=movies")
    _item("TV Shows", f"{_BASE}?category=shows")
    _item("Favourites", f"{_BASE}?category=favourites")

    # Trakt sections appear only once the user has authenticated
    try:
        from services.trakt import Trakt
        if Trakt.is_authenticated():
            _item("Trakt Watchlist", f"{_BASE}?category=trakt&subcategory=watchlist")
            _item("Trakt Recommendations", f"{_BASE}?category=trakt&subcategory=recommendations")
    except Exception:
        pass

    _item("Settings", f"{_BASE}?category=settings")
    xbmcplugin.endOfDirectory(HANDLE)


def _item(label: str, url: str, is_folder: bool = True):
    li = xbmcgui.ListItem(label=label)
    xbmcplugin.addDirectoryItem(HANDLE, url, li, isFolder=is_folder)
