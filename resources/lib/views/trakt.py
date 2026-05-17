import sys
import xbmcgui
import xbmcplugin
from typing import Any
from urllib.parse import quote_plus

from services.trakt import Trakt, PAGE_SIZE
from services.tmdb import Tmdb
from utils.notifications import error

HANDLE = int(sys.argv[1])
_BASE = sys.argv[0]
_IMG = "https://image.tmdb.org/t/p/w500"


def show_trakt_categories(subcategory: str):
    items = [("Movies", f"?category=trakt&subcategory={subcategory}_movies"),
             ("TV Shows", f"?category=trakt&subcategory={subcategory}_shows")]
    for label, qs in items:
        li = xbmcgui.ListItem(label=label)
        xbmcplugin.addDirectoryItem(HANDLE, f"{_BASE}{qs}", li, isFolder=True)
    xbmcplugin.endOfDirectory(HANDLE)


# ── Watchlist ─────────────────────────────────────────────────────────────────

def show_trakt_watchlist_movies(page: int = 1):
    try:
        items = Trakt.watchlist_movies(page=page)
    except Exception as e:
        error(f"Trakt error: {e}")
        xbmcplugin.endOfDirectory(HANDLE)
        return

    xbmcplugin.setContent(HANDLE, "movies")
    for item in items:
        _add_watchlist_movie(item)

    if len(items) >= PAGE_SIZE:
        li = xbmcgui.ListItem(label=f"Next Page → ({page + 1})")
        xbmcplugin.addDirectoryItem(
            HANDLE, f"{_BASE}?category=trakt&subcategory=watchlist_movies&page={page + 1}", li, isFolder=True
        )
    xbmcplugin.endOfDirectory(HANDLE)


def show_trakt_watchlist_shows(page: int = 1):
    try:
        items = Trakt.watchlist_shows(page=page)
    except Exception as e:
        error(f"Trakt error: {e}")
        xbmcplugin.endOfDirectory(HANDLE)
        return

    xbmcplugin.setContent(HANDLE, "tvshows")
    for item in items:
        _add_watchlist_show(item)

    if len(items) >= PAGE_SIZE:
        li = xbmcgui.ListItem(label=f"Next Page → ({page + 1})")
        xbmcplugin.addDirectoryItem(
            HANDLE, f"{_BASE}?category=trakt&subcategory=watchlist_shows&page={page + 1}", li, isFolder=True
        )
    xbmcplugin.endOfDirectory(HANDLE)


# ── Recommendations ───────────────────────────────────────────────────────────

def show_trakt_recommendations_movies(page: int = 1):
    try:
        items = Trakt.recommendations_movies(page=page)
    except Exception as e:
        error(f"Trakt error: {e}")
        xbmcplugin.endOfDirectory(HANDLE)
        return

    xbmcplugin.setContent(HANDLE, "movies")
    for item in items:
        _add_recommendation_movie(item)

    if len(items) >= PAGE_SIZE:
        li = xbmcgui.ListItem(label=f"Next Page → ({page + 1})")
        xbmcplugin.addDirectoryItem(
            HANDLE, f"{_BASE}?category=trakt&subcategory=recommendations_movies&page={page + 1}", li, isFolder=True
        )
    xbmcplugin.endOfDirectory(HANDLE)


def show_trakt_recommendations_shows(page: int = 1):
    try:
        items = Trakt.recommendations_shows(page=page)
    except Exception as e:
        error(f"Trakt error: {e}")
        xbmcplugin.endOfDirectory(HANDLE)
        return

    xbmcplugin.setContent(HANDLE, "tvshows")
    for item in items:
        _add_recommendation_show(item)

    if len(items) >= PAGE_SIZE:
        li = xbmcgui.ListItem(label=f"Next Page → ({page + 1})")
        xbmcplugin.addDirectoryItem(
            HANDLE, f"{_BASE}?category=trakt&subcategory=recommendations_shows&page={page + 1}", li, isFolder=True
        )
    xbmcplugin.endOfDirectory(HANDLE)


# ── Item renderers ────────────────────────────────────────────────────────────

def _tmdb_images(tmdb_id: int, media: str) -> tuple[str, str]:
    """Fetch poster_path and backdrop_path from TMDB. Returns ('', '') on failure."""
    try:
        d = Tmdb.movie_details(tmdb_id) if media == "movie" else Tmdb.tv_details(tmdb_id)
        return d.get("poster_path") or "", d.get("backdrop_path") or ""
    except Exception:
        return "", ""


def _add_watchlist_movie(item: dict[str, Any]):
    movie = item.get("movie", {})
    tmdb_id: int | None = movie.get("ids", {}).get("tmdb")
    title = movie.get("title", "Unknown")
    year = int(movie.get("year") or 0)
    overview = movie.get("overview", "")

    poster, backdrop = _tmdb_images(tmdb_id, "movie") if tmdb_id else ("", "")

    li = xbmcgui.ListItem(label=f"{title} ({year})" if year else title)
    li.setProperty("IsPlayable", "true")
    li.setInfo("video", {"title": title, "plot": overview, "year": year, "mediatype": "movie"})
    li.setArt({
        "thumb": f"{_IMG}{poster}" if poster else "",
        "poster": f"{_IMG}{poster}" if poster else "",
        "fanart": f"{_IMG}{backdrop}" if backdrop else "",
    })
    if tmdb_id:
        _attach_fav_menu(li, "movie", tmdb_id, title, str(year), poster)
        xbmcplugin.addDirectoryItem(HANDLE, f"{_BASE}?action=play&type=movie&id={tmdb_id}", li, isFolder=False)


def _add_watchlist_show(item: dict[str, Any]):
    show = item.get("show", {})
    tmdb_id: int | None = show.get("ids", {}).get("tmdb")
    title = show.get("title", "Unknown")
    year = int(show.get("year") or 0)
    overview = show.get("overview", "")

    poster, backdrop = _tmdb_images(tmdb_id, "tv") if tmdb_id else ("", "")

    li = xbmcgui.ListItem(label=f"{title} ({year})" if year else title)
    li.setInfo("video", {"title": title, "plot": overview, "year": year, "mediatype": "tvshow"})
    li.setArt({
        "thumb": f"{_IMG}{poster}" if poster else "",
        "poster": f"{_IMG}{poster}" if poster else "",
        "fanart": f"{_IMG}{backdrop}" if backdrop else "",
    })
    if tmdb_id:
        _attach_fav_menu(li, "show", tmdb_id, title, str(year), poster)
        url = f"{_BASE}?action=seasons&show_id={tmdb_id}&show_title={quote_plus(title)}"
        xbmcplugin.addDirectoryItem(HANDLE, url, li, isFolder=True)


def _add_recommendation_movie(item: dict[str, Any]):
    tmdb_id: int | None = item.get("ids", {}).get("tmdb")
    title = item.get("title", "Unknown")
    year = int(item.get("year") or 0)
    overview = item.get("overview", "")

    poster, backdrop = _tmdb_images(tmdb_id, "movie") if tmdb_id else ("", "")

    li = xbmcgui.ListItem(label=f"{title} ({year})" if year else title)
    li.setProperty("IsPlayable", "true")
    li.setInfo("video", {"title": title, "plot": overview, "year": year, "mediatype": "movie"})
    li.setArt({
        "thumb": f"{_IMG}{poster}" if poster else "",
        "poster": f"{_IMG}{poster}" if poster else "",
        "fanart": f"{_IMG}{backdrop}" if backdrop else "",
    })
    if tmdb_id:
        _attach_fav_menu(li, "movie", tmdb_id, title, str(year), poster)
        xbmcplugin.addDirectoryItem(HANDLE, f"{_BASE}?action=play&type=movie&id={tmdb_id}", li, isFolder=False)


def _add_recommendation_show(item: dict[str, Any]):
    tmdb_id: int | None = item.get("ids", {}).get("tmdb")
    title = item.get("title", "Unknown")
    year = int(item.get("year") or 0)
    overview = item.get("overview", "")

    poster, backdrop = _tmdb_images(tmdb_id, "tv") if tmdb_id else ("", "")

    li = xbmcgui.ListItem(label=f"{title} ({year})" if year else title)
    li.setInfo("video", {"title": title, "plot": overview, "year": year, "mediatype": "tvshow"})
    li.setArt({
        "thumb": f"{_IMG}{poster}" if poster else "",
        "poster": f"{_IMG}{poster}" if poster else "",
        "fanart": f"{_IMG}{backdrop}" if backdrop else "",
    })
    if tmdb_id:
        _attach_fav_menu(li, "show", tmdb_id, title, str(year), poster)
        url = f"{_BASE}?action=seasons&show_id={tmdb_id}&show_title={quote_plus(title)}"
        xbmcplugin.addDirectoryItem(HANDLE, url, li, isFolder=True)


def _attach_fav_menu(li: xbmcgui.ListItem, item_type: str, tmdb_id: int, title: str, year: str, poster: str):
    fav_url = (
        f"{_BASE}?action=favourite_add&type={item_type}&id={tmdb_id}"
        f"&title={quote_plus(title)}&year={year}&poster={quote_plus(poster)}"
    )
    li.addContextMenuItems([("Add to Favourites", f"RunPlugin({fav_url})")])
