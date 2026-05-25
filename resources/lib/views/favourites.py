import json
import os
import sys
import xbmcaddon
import xbmcgui
import xbmcplugin
import xbmcvfs
from typing import Any
from urllib.parse import quote_plus

HANDLE = int(sys.argv[1])
_BASE = sys.argv[0]
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
        poster = fav.get("poster", "")
        key = fav.get("key", "")

        label = f"{title} ({year})" if year else title
        li = xbmcgui.ListItem(label=label)
        li.setArt({
            "thumb": f"{_IMG}{poster}" if poster else "",
            "poster": f"{_IMG}{poster}" if poster else "",
        })

        remove_url = f"{_BASE}?action=favourite_remove&key={quote_plus(key)}"
        wl_type = "movie" if item_type == "movie" else "show"
        wl_url = f"{_BASE}?action=trakt_watchlist_add&type={wl_type}&id={tmdb_id}"
        mw_url = f"{_BASE}?action=trakt_mark_watched&type={wl_type}&id={tmdb_id}"
        li.addContextMenuItems([
            ("Remove from Favourites", f"RunPlugin({remove_url})"),
            ("Add to Trakt Watchlist", f"RunPlugin({wl_url})"),
            ("Mark as Watched", f"RunPlugin({mw_url})"),
        ])

        if item_type == "movie":
            li.setProperty("IsPlayable", "true")
            li.setInfo("video", {
                "title": title,
                "year": int(year) if year.isdigit() else 0,
                "mediatype": "movie",
            })
            _ = xbmcplugin.addDirectoryItem(
                HANDLE, f"{_BASE}?action=play&type=movie&id={tmdb_id}", li, isFolder=False
            )
        else:
            li.setInfo("video", {
                "title": title,
                "year": int(year) if year.isdigit() else 0,
                "mediatype": "tvshow",
            })
            url = f"{_BASE}?action=seasons&show_id={tmdb_id}&show_title={quote_plus(title)}"
            _ = xbmcplugin.addDirectoryItem(HANDLE, url, li, isFolder=True)

    xbmcplugin.endOfDirectory(HANDLE)
