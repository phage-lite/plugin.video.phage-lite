import sys
import xbmcaddon
import xbmcgui
import xbmcplugin

HANDLE = int(sys.argv[1])
_BASE = sys.argv[0]


def show_home():
    _first_run_check()

    _item("Search", f"{_BASE}?action=search")
    _item("Movies", f"{_BASE}?category=movies")
    _item("TV Shows", f"{_BASE}?category=shows")
    _item("Favourites", f"{_BASE}?category=favourites")

    try:
        from services.trakt import Trakt
        if Trakt.is_authenticated():
            _item("Up Next", f"{_BASE}?category=trakt&subcategory=upnext")
            _item("Trakt Watchlist", f"{_BASE}?category=trakt&subcategory=watchlist")
            _item("Trakt Recommendations", f"{_BASE}?category=trakt&subcategory=recommendations")
    except Exception:
        pass

    _item("Settings", f"{_BASE}?category=settings")
    xbmcplugin.endOfDirectory(HANDLE)


def _first_run_check():
    try:
        from services.real_debrid import RealDebrid
        if RealDebrid.is_authenticated():
            return
        win = xbmcgui.Window(10000)
        if win.getProperty("bacterio.welcome_shown"):
            return
        win.setProperty("bacterio.welcome_shown", "1")
        go = xbmcgui.Dialog().yesno(
            "Welcome to Bacterio!",
            (
                "To stream movies and TV shows you need a [B]Real Debrid[/B] subscription.\n\n"
                "Open Settings now to connect your account?"
            ),
            nolabel="Later",
            yeslabel="Open Settings",
        )
        if go:
            xbmcaddon.Addon().openSettings()
    except Exception:
        pass


def _item(label: str, url: str, is_folder: bool = True):
    li = xbmcgui.ListItem(label=label)
    xbmcplugin.addDirectoryItem(HANDLE, url, li, isFolder=is_folder)
