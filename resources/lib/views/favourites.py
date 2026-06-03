import json
import os
import sys
import xbmcaddon
import xbmcgui
import xbmcplugin
import xbmcvfs
from typing import Any

from items import MovieItem, ShowItem
from services.tmdb import Tmdb
from utils.router import url

HANDLE = int(sys.argv[1])
_IMG = "https://image.tmdb.org/t/p/w500"


def _favs_path() -> str:
    profile = xbmcvfs.translatePath(xbmcaddon.Addon().getAddonInfo("profile"))
    os.makedirs(profile, exist_ok=True)
    return os.path.join(profile, "favourites.json")


def _load() -> list[dict[str, Any]]:
    path = _favs_path()
    try:
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return []


def _save(favs: list[dict[str, Any]]) -> None:
    try:
        with open(_favs_path(), "w", encoding="utf-8") as f:
            json.dump(favs, f, indent=2)
    except Exception:
        pass


def add_favourite(item_type: str, tmdb_id: str, title: str, year: str = "", poster: str = "") -> None:
    favs = _load()
    key = f"{item_type}:{tmdb_id}"
    if any(f.get("key") == key for f in favs):
        xbmcgui.Dialog().notification("Bacterio", "Already in Favourites", time=2000)
        return
    favs.append({"key": key, "type": item_type, "tmdb_id": tmdb_id,
                 "title": title, "year": year, "poster": poster})
    _save(favs)
    xbmcgui.Dialog().notification("Bacterio", f"Added: {title}", time=2000)


def remove_favourite(key: str) -> None:
    favs = _load()
    entry = next((f for f in favs if f.get("key") == key), None)
    favs = [f for f in favs if f.get("key") != key]
    _save(favs)
    if entry:
        xbmcgui.Dialog().notification("Bacterio", f"Removed: {entry.get('title', '')}", time=2000)


def show_movie_favourites() -> None:
    _show_filtered("movie")


def show_show_favourites() -> None:
    _show_filtered("show")


def _show_filtered(filter_type: str) -> None:
    favs = [f for f in _load() if f.get("type") == filter_type]
    if not favs:
        label = "Movies" if filter_type == "movie" else "TV Shows"
        _ = xbmcgui.Dialog().ok(
            f"My {label}",
            f"No favourite {label.lower()} yet.\n\nLong-press any item and choose Add to Favourites.",
        )
        xbmcplugin.endOfDirectory(HANDLE)
        return
    _render_favourites(favs)


def show_favourites() -> None:
    favs = _load()
    if not favs:
        _ = xbmcgui.Dialog().ok(
            "Favourites",
            "No favourites yet.\n\nLong-press any movie or show and choose Add to Favourites.",
        )
        xbmcplugin.endOfDirectory(HANDLE)
        return
    _render_favourites(favs)


def _render_favourites(favs: list[dict[str, Any]]) -> None:
    for fav in favs:
        item_type = fav.get("type", "movie")
        tmdb_id = fav.get("tmdb_id", "")
        title = fav.get("title", "Unknown")
        year = fav.get("year", "")
        key = fav.get("key", "")

        remove_url = url("/favourite/remove/", key=key)
        wl_type = "movie" if item_type == "movie" else "show"
        wl_url = url("/trakt/watchlist/add/", type=wl_type, id=tmdb_id)
        mw_url = url("/trakt/watched/", type=wl_type, id=tmdb_id)
        context_menus = [
            ("Remove from Favourites", f"RunPlugin({remove_url})"),
            ("Add to Trakt Watchlist", f"RunPlugin({wl_url})"),
            ("Mark as Watched", f"RunPlugin({mw_url})"),
        ]

        if item_type == "movie":
            try:
                details = Tmdb.movie_rich_details(int(tmdb_id))
            except Exception:
                continue
            li = MovieItem(details).build()
            li.addContextMenuItems(context_menus)
            _ = xbmcplugin.addDirectoryItem(HANDLE, url("/play/", type="movie", id=tmdb_id), li, isFolder=False)
        else:
            try:
                details = Tmdb.tv_show_details(int(tmdb_id))
            except Exception:
                continue
            li = ShowItem(details).build()
            li.addContextMenuItems(context_menus)
            show_url = url("/show/:show_id/seasons/", show_id=tmdb_id, show_title=title)
            _ = xbmcplugin.addDirectoryItem(HANDLE, show_url, li, isFolder=True)

    xbmcplugin.endOfDirectory(HANDLE)
