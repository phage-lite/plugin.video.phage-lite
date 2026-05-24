import sys
import xbmcgui
import xbmcplugin
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any
from urllib.parse import quote_plus

from services.trakt import Trakt, PAGE_SIZE
from services.tmdb import Tmdb
from utils.notifications import error

HANDLE = int(sys.argv[1])
_BASE = sys.argv[0]
_IMG = "https://image.tmdb.org/t/p/w500"


# ── Context menu helpers ──────────────────────────────────────────────────────

def _menus_browse(media_type: str, tmdb_id: int, title: str, year: str, poster: str) -> list[tuple[str, str]]:
    """Menus for items NOT in the watchlist — offer to add."""
    fav = (
        f"{_BASE}?action=favourite_add&type={media_type}&id={tmdb_id}"
        f"&title={quote_plus(title)}&year={year}&poster={quote_plus(poster)}"
    )
    wl = f"{_BASE}?action=trakt_watchlist_add&type={media_type}&id={tmdb_id}"
    return [
        ("Add to Favourites", f"RunPlugin({fav})"),
        ("Add to Trakt Watchlist", f"RunPlugin({wl})"),
    ]


def _menus_watchlist(media_type: str, tmdb_id: int, title: str, year: str, poster: str) -> list[tuple[str, str]]:
    """Menus for items already in the Trakt watchlist — offer to remove."""
    fav = (
        f"{_BASE}?action=favourite_add&type={media_type}&id={tmdb_id}"
        f"&title={quote_plus(title)}&year={year}&poster={quote_plus(poster)}"
    )
    rem = f"{_BASE}?action=trakt_watchlist_remove&type={media_type}&id={tmdb_id}"
    return [
        ("Add to Favourites", f"RunPlugin({fav})"),
        ("Remove from Trakt Watchlist", f"RunPlugin({rem})"),
    ]


# ── Category chooser ──────────────────────────────────────────────────────────

def show_trakt_categories(subcategory: str):
    items = [
        ("Movies", f"?category=trakt&subcategory={subcategory}_movies"),
        ("TV Shows", f"?category=trakt&subcategory={subcategory}_shows"),
    ]
    for label, qs in items:
        li = xbmcgui.ListItem(label=label)
        xbmcplugin.addDirectoryItem(HANDLE, f"{_BASE}{qs}", li, isFolder=True)
    xbmcplugin.endOfDirectory(HANDLE)


# ── Up Next ───────────────────────────────────────────────────────────────────

def show_up_next():
    try:
        items = _fetch_up_next()
    except Exception as e:
        error(f"Up Next error: {e}")
        xbmcplugin.endOfDirectory(HANDLE)
        return

    if not items:
        xbmcgui.Dialog().ok(
            "Up Next",
            "Nothing up next.\n\nAdd shows to your Trakt Watchlist and watch some episodes to get started.",
        )
        xbmcplugin.endOfDirectory(HANDLE)
        return

    xbmcplugin.setContent(HANDLE, "episodes")
    for item in items:
        _add_up_next_item(item)
    xbmcplugin.endOfDirectory(HANDLE)


def _fetch_up_next() -> list[dict[str, Any]]:
    watchlist = Trakt.watchlist_shows(limit=20)

    def _progress(wl_item: dict[str, Any]) -> dict[str, Any] | None:
        show = wl_item.get("show", {})
        trakt_id: int | None = show.get("ids", {}).get("trakt")
        tmdb_id: int | None = show.get("ids", {}).get("tmdb")
        if not trakt_id or not tmdb_id:
            return None
        try:
            prog = Trakt.show_progress(trakt_id)
            next_ep = prog.get("next_episode")
            if not next_ep:
                return None
            poster, backdrop = _tmdb_images(tmdb_id, "tv")
            return {
                "title":   show.get("title", "Unknown"),
                "tmdb_id": tmdb_id,
                "season":  int(next_ep.get("season") or 1),
                "episode": int(next_ep.get("number") or 1),
                "ep_title": next_ep.get("title") or "",
                "poster":  poster,
                "backdrop": backdrop,
            }
        except Exception:
            return None

    results: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(_progress, item) for item in watchlist]
        for future in as_completed(futures):
            val = future.result()
            if val:
                results.append(val)

    results.sort(key=lambda x: (x["title"], x["season"], x["episode"]))
    return results


def _add_up_next_item(item: dict[str, Any]):
    title = item["title"]
    season = item["season"]
    episode = item["episode"]
    ep_title = item.get("ep_title") or f"Episode {episode}"
    tmdb_id = item["tmdb_id"]
    poster = item.get("poster", "")
    backdrop = item.get("backdrop", "")

    label = f"{title}  S{season:02d}E{episode:02d}"
    if ep_title and ep_title != f"Episode {episode}":
        label += f" · {ep_title}"

    li = xbmcgui.ListItem(label=label)
    li.setProperty("IsPlayable", "true")
    li.setInfo("video", {
        "title": ep_title,
        "tvshowtitle": title,
        "season": season,
        "episode": episode,
        "mediatype": "episode",
    })
    li.setArt({
        "thumb": f"{_IMG}{backdrop}" if backdrop else f"{_IMG}{poster}" if poster else "",
        "poster": f"{_IMG}{poster}" if poster else "",
        "fanart": f"{_IMG}{backdrop}" if backdrop else "",
    })
    url = (
        f"{_BASE}?action=play&type=episode"
        f"&id={tmdb_id}&season={season}&episode={episode}"
    )
    xbmcplugin.addDirectoryItem(HANDLE, url, li, isFolder=False)


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
    try:
        d = Tmdb.movie_details(tmdb_id) if media == "movie" else Tmdb.tv_details(tmdb_id)
        return d.get("poster_path") or "", d.get("backdrop_path") or ""
    except Exception:
        return "", ""


def _add_watchlist_movie(item: dict[str, Any]):
    movie = item.get("movie", {})
    tmdb_id: int = int(movie.get("ids", {}).get("tmdb") or 0)
    title = movie.get("title", "Unknown")
    year = int(movie.get("year") or 0)
    overview = movie.get("overview", "")
    year_str = str(year) if year else ""

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
        li.addContextMenuItems(_menus_watchlist("movie", tmdb_id, title, year_str, poster))
        xbmcplugin.addDirectoryItem(HANDLE, f"{_BASE}?action=play&type=movie&id={tmdb_id}", li, isFolder=False)


def _add_watchlist_show(item: dict[str, Any]):
    show = item.get("show", {})
    tmdb_id: int = int(show.get("ids", {}).get("tmdb") or 0)
    title = show.get("title", "Unknown")
    year = int(show.get("year") or 0)
    overview = show.get("overview", "")
    year_str = str(year) if year else ""

    poster, backdrop = _tmdb_images(tmdb_id, "tv") if tmdb_id else ("", "")

    li = xbmcgui.ListItem(label=f"{title} ({year})" if year else title)
    li.setInfo("video", {"title": title, "plot": overview, "year": year, "mediatype": "tvshow"})
    li.setArt({
        "thumb": f"{_IMG}{poster}" if poster else "",
        "poster": f"{_IMG}{poster}" if poster else "",
        "fanart": f"{_IMG}{backdrop}" if backdrop else "",
    })
    if tmdb_id:
        li.addContextMenuItems(_menus_watchlist("show", tmdb_id, title, year_str, poster))
        url = f"{_BASE}?action=seasons&show_id={tmdb_id}&show_title={quote_plus(title)}"
        xbmcplugin.addDirectoryItem(HANDLE, url, li, isFolder=True)


def _add_recommendation_movie(item: dict[str, Any]):
    tmdb_id: int = int(item.get("ids", {}).get("tmdb") or 0)
    title = item.get("title", "Unknown")
    year = int(item.get("year") or 0)
    overview = item.get("overview", "")
    year_str = str(year) if year else ""

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
        li.addContextMenuItems(_menus_browse("movie", tmdb_id, title, year_str, poster))
        xbmcplugin.addDirectoryItem(HANDLE, f"{_BASE}?action=play&type=movie&id={tmdb_id}", li, isFolder=False)


def _add_recommendation_show(item: dict[str, Any]):
    tmdb_id: int = int(item.get("ids", {}).get("tmdb") or 0)
    title = item.get("title", "Unknown")
    year = int(item.get("year") or 0)
    overview = item.get("overview", "")
    year_str = str(year) if year else ""

    poster, backdrop = _tmdb_images(tmdb_id, "tv") if tmdb_id else ("", "")

    li = xbmcgui.ListItem(label=f"{title} ({year})" if year else title)
    li.setInfo("video", {"title": title, "plot": overview, "year": year, "mediatype": "tvshow"})
    li.setArt({
        "thumb": f"{_IMG}{poster}" if poster else "",
        "poster": f"{_IMG}{poster}" if poster else "",
        "fanart": f"{_IMG}{backdrop}" if backdrop else "",
    })
    if tmdb_id:
        li.addContextMenuItems(_menus_browse("show", tmdb_id, title, year_str, poster))
        url = f"{_BASE}?action=seasons&show_id={tmdb_id}&show_title={quote_plus(title)}"
        xbmcplugin.addDirectoryItem(HANDLE, url, li, isFolder=True)
