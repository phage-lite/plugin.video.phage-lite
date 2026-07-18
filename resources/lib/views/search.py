import json
import os
import sys
import xbmcaddon
import xbmcgui
import xbmcplugin
import xbmcvfs
from typing import Any

from menu_items.movie import MovieItem
from menu_items.show import ShowItem
from services.tmdb import Tmdb
from utils.notifications import error
from utils.router import url

HANDLE = int(sys.argv[1])
_IMG = "https://image.tmdb.org/t/p/w500"
_HISTORY_LIMIT = 25


# ── Search history ────────────────────────────────────────────────────────────


def _history_path() -> str:
    profile = xbmcvfs.translatePath(xbmcaddon.Addon().getAddonInfo("profile"))
    os.makedirs(profile, exist_ok=True)
    return os.path.join(profile, "search_history.json")


def _load_history() -> list[str]:
    try:
        path = _history_path()
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return []


def _save_history(query: str) -> None:
    try:
        history = [q for q in _load_history() if q.lower() != query.lower()]
        history.insert(0, query)
        with open(_history_path(), "w", encoding="utf-8") as f:
            json.dump(history[:_HISTORY_LIMIT], f)
    except Exception:
        pass


def _clear_history() -> None:
    try:
        path = _history_path()
        if os.path.exists(path):
            os.remove(path)
    except Exception:
        pass


# ── Context menus ─────────────────────────────────────────────────────────────


def _menus(
    media_type: str, tmdb_id: int, title: str, year: str, poster: str
) -> list[tuple[str, str]]:
    fav = url(
        "/favourite/add/",
        type=media_type,
        id=tmdb_id,
        title=title,
        year=year,
        poster=poster,
    )
    wl = url("/trakt/watchlist/add/", type=media_type, id=tmdb_id)
    return [
        ("Add to Favourites", f"RunPlugin({fav})"),
        ("Add to Trakt Watchlist", f"RunPlugin({wl})"),
    ]


# ── Public API ────────────────────────────────────────────────────────────────


def do_search(query: str = "", page: int = 1):
    if not query:
        query = _prompt_with_history()
        if not query:
            xbmcplugin.endOfDirectory(HANDLE, succeeded=False)
            return

    _save_history(query)

    try:
        data = Tmdb.search(query, page)
    except Exception as e:
        error(f"Search failed: {e}")
        xbmcplugin.endOfDirectory(HANDLE)
        return

    results = [
        r for r in data.get("results", []) if r.get("media_type") in ("movie", "tv")
    ]
    total_pages: int = data.get("total_pages", 1)

    if not results:
        _ = xbmcgui.Dialog().ok("No results", f'Nothing found for "{query}".')
        xbmcplugin.endOfDirectory(HANDLE)
        return

    xbmcplugin.setContent(HANDLE, "movies")

    for item in results:
        if item.get("media_type") == "movie":
            _add_movie(item)
        else:
            _add_show(item)

    if page < total_pages:
        next_url = url("/search/", query=query, page=page + 1)
        li = xbmcgui.ListItem(label=f"Next Page → ({page + 1} / {total_pages})")
        li.setProperty("SpecialSort", "bottom")
        p = os.path.join(
            xbmcaddon.Addon().getAddonInfo("path"),
            "resources",
            "media",
            "icons",
            "nextpage.png",
        )
        li.setArt({"icon": p, "thumb": p, "poster": p})
        _ = xbmcplugin.addDirectoryItem(HANDLE, next_url, li, isFolder=True)

    xbmcplugin.endOfDirectory(HANDLE)


def clear_search_history():
    _clear_history()
    xbmcgui.Dialog().notification("Bacterio", "Search history cleared", time=2000)


# ── Prompt helpers ────────────────────────────────────────────────────────────


def _prompt_with_history() -> str:
    history = _load_history()
    if not history:
        return xbmcgui.Dialog().input("Search for anything") or ""

    options = ["New search..."] + history + ["--- Clear history ---"]
    idx = xbmcgui.Dialog().select("Search", list(options))
    if idx < 0:
        return ""
    if idx == 0:
        return xbmcgui.Dialog().input("Search for anything") or ""
    if idx == len(options) - 1:
        _clear_history()
        xbmcgui.Dialog().notification("Bacterio", "History cleared", time=1500)
        return xbmcgui.Dialog().input("Search for anything") or ""
    return history[idx - 1]


# ── Item renderers ────────────────────────────────────────────────────────────


def _add_movie(movie: dict[str, Any]):
    tmdb_id = int(movie.get("id") or 0)
    title = movie.get("title", "Unknown")
    try:
        details = Tmdb.movie_rich_details(tmdb_id)
    except Exception:
        return
    movie_item = MovieItem(details)
    movie_item.listItem.setLabel(f"[MOVIE] {title}")
    movie_item.listItem.setLabel2(f"[MOVIE] {title}")
    _ = xbmcplugin.addDirectoryItem(
        HANDLE, movie_item.url, movie_item.listItem, isFolder=False
    )


def _add_show(show: dict[str, Any]):
    tmdb_id = int(show.get("id") or 0)
    title = show.get("name", "Unknown")
    try:
        details = Tmdb.tv_show_details(tmdb_id)
    except Exception:
        return
    show_item = ShowItem(details)
    show_item.listItem.setLabel(f"[TV] {title}")
    _ = xbmcplugin.addDirectoryItem(
        HANDLE, show_item.url, show_item.listItem, isFolder=True
    )
