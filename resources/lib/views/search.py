import sys
import xbmcgui
import xbmcplugin
from typing import Any
from urllib.parse import quote_plus

from services.tmdb import Tmdb
from utils.notifications import error

HANDLE = int(sys.argv[1])
_BASE = sys.argv[0]
_IMG = "https://image.tmdb.org/t/p/w500"


def do_search(query: str = "", page: int = 1):
    if not query:
        query = xbmcgui.Dialog().input("Search")
        if not query:
            xbmcplugin.endOfDirectory(HANDLE, succeeded=False)
            return

    try:
        data = Tmdb.search(query, page)
    except Exception as e:
        error(f"Search failed: {e}")
        xbmcplugin.endOfDirectory(HANDLE)
        return

    results = [r for r in data.get("results", []) if r.get("media_type") in ("movie", "tv")]
    total_pages: int = data.get("total_pages", 1)

    xbmcplugin.setContent(HANDLE, "movies")

    for item in results:
        if item.get("media_type") == "movie":
            _add_movie(item)
        else:
            _add_show(item)

    if page < total_pages:
        li = xbmcgui.ListItem(label=f"Next Page → ({page + 1} / {total_pages})")
        next_url = f"{_BASE}?action=search&query={quote_plus(query)}&page={page + 1}"
        xbmcplugin.addDirectoryItem(HANDLE, next_url, li, isFolder=True)

    xbmcplugin.endOfDirectory(HANDLE)


def _add_movie(movie: dict[str, Any]):
    title = movie.get("title", "Unknown")
    overview = movie.get("overview", "")
    poster = movie.get("poster_path") or ""
    backdrop = movie.get("backdrop_path") or ""
    rating = float(movie.get("vote_average") or 0)
    year_str = (movie.get("release_date") or "")[:4]
    tmdb_id = movie.get("id")

    li = xbmcgui.ListItem(label=f"[MOVIE] {title}")
    li.setProperty("IsPlayable", "true")
    li.setInfo("video", {
        "title": title,
        "plot": overview,
        "year": int(year_str) if year_str.isdigit() else 0,
        "rating": rating,
        "mediatype": "movie",
    })
    li.setArt({
        "thumb": f"{_IMG}{poster}" if poster else "",
        "poster": f"{_IMG}{poster}" if poster else "",
        "fanart": f"{_IMG}{backdrop}" if backdrop else "",
    })
    fav_url = (
        f"{_BASE}?action=favourite_add&type=movie&id={tmdb_id}"
        f"&title={quote_plus(title)}&year={year_str}&poster={quote_plus(poster)}"
    )
    li.addContextMenuItems([("Add to Favourites", f"RunPlugin({fav_url})")])
    xbmcplugin.addDirectoryItem(HANDLE, f"{_BASE}?action=play&type=movie&id={tmdb_id}", li, isFolder=False)


def _add_show(show: dict[str, Any]):
    title = show.get("name", "Unknown")
    overview = show.get("overview", "")
    poster = show.get("poster_path") or ""
    backdrop = show.get("backdrop_path") or ""
    rating = float(show.get("vote_average") or 0)
    year_str = (show.get("first_air_date") or "")[:4]
    tmdb_id = show.get("id")

    li = xbmcgui.ListItem(label=f"[TV] {title}")
    li.setInfo("video", {
        "title": title,
        "plot": overview,
        "year": int(year_str) if year_str.isdigit() else 0,
        "rating": rating,
        "mediatype": "tvshow",
    })
    li.setArt({
        "thumb": f"{_IMG}{poster}" if poster else "",
        "poster": f"{_IMG}{poster}" if poster else "",
        "fanart": f"{_IMG}{backdrop}" if backdrop else "",
    })
    fav_url = (
        f"{_BASE}?action=favourite_add&type=show&id={tmdb_id}"
        f"&title={quote_plus(title)}&year={year_str}&poster={quote_plus(poster)}"
    )
    li.addContextMenuItems([("Add to Favourites", f"RunPlugin({fav_url})")])
    url = f"{_BASE}?action=seasons&show_id={tmdb_id}&show_title={quote_plus(title)}"
    xbmcplugin.addDirectoryItem(HANDLE, url, li, isFolder=True)
