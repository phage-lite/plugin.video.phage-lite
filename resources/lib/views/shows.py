import sys
import xbmcgui
import xbmcplugin
from typing import Any, Callable
from urllib.parse import quote_plus

from services.tmdb import Tmdb
from utils.notifications import error

HANDLE = int(sys.argv[1])
_BASE = sys.argv[0]
_IMG = "https://image.tmdb.org/t/p/w500"

_SUBCATEGORIES = [
    ("Popular", "popular"),
    ("Trending", "trending"),
    ("Airing Today", "airing_today"),
    ("On Air This Week", "on_air"),
    ("Top Rated", "top_rated"),
    ("Genres", "genres"),
]

_FETCHERS: dict[str, Callable[[int], dict[str, Any]]] = {
    "popular":      lambda page: Tmdb.popular_tv(page),
    "trending":     lambda page: Tmdb.trending_tv(page=page),
    "airing_today": lambda page: Tmdb.airing_today_tv(page),
    "on_air":       lambda page: Tmdb.on_air_tv(page),
    "top_rated":    lambda page: Tmdb.top_rated_tv(page),
}

_genre_cache: dict[int, str] = {}


def _ensure_genres() -> None:
    global _genre_cache
    if not _genre_cache:
        try:
            genres = Tmdb.tv_genres().get("genres", [])
            _genre_cache = {int(g["id"]): str(g["name"]) for g in genres}
        except Exception:
            pass


def _genre_str(ids: list[int]) -> str:
    _ensure_genres()
    return " / ".join(_genre_cache[g] for g in ids[:3] if g in _genre_cache)


def _menus(media_type: str, tmdb_id: int, title: str, year: str, poster: str) -> list[tuple[str, str]]:
    fav = (
        f"{_BASE}?action=favourite_add&type={media_type}&id={tmdb_id}"
        f"&title={quote_plus(title)}&year={year}&poster={quote_plus(poster)}"
    )
    wl = f"{_BASE}?action=trakt_watchlist_add&type={media_type}&id={tmdb_id}"
    return [
        ("Add to Favourites", f"RunPlugin({fav})"),
        ("Add to Trakt Watchlist", f"RunPlugin({wl})"),
    ]


def show_tv_categories():
    for label, key in _SUBCATEGORIES:
        li = xbmcgui.ListItem(label=label)
        _ = xbmcplugin.addDirectoryItem(HANDLE, f"{_BASE}?category=shows&subcategory={key}", li, isFolder=True)

    li = xbmcgui.ListItem(label="My Favourites")
    _ = xbmcplugin.addDirectoryItem(HANDLE, f"{_BASE}?category=shows&subcategory=favourites", li, isFolder=True)

    try:
        from services.trakt import Trakt
        if Trakt.is_authenticated():
            li = xbmcgui.ListItem(label="Up Next")
            _ = xbmcplugin.addDirectoryItem(HANDLE, f"{_BASE}?category=shows&subcategory=upnext", li, isFolder=True)
            li = xbmcgui.ListItem(label="Trakt Watchlist")
            _ = xbmcplugin.addDirectoryItem(HANDLE, f"{_BASE}?category=shows&subcategory=trakt_watchlist", li, isFolder=True)
            li = xbmcgui.ListItem(label="Trakt Recommendations")
            _ = xbmcplugin.addDirectoryItem(HANDLE, f"{_BASE}?category=shows&subcategory=trakt_recommendations", li, isFolder=True)
            li = xbmcgui.ListItem(label="My Calendar")
            _ = xbmcplugin.addDirectoryItem(HANDLE, f"{_BASE}?category=shows&subcategory=calendar", li, isFolder=True)
    except Exception:
        pass

    xbmcplugin.endOfDirectory(HANDLE)


def show_tv_list(subcategory: str, page: int = 1):
    fetch = _FETCHERS.get(subcategory)
    if fetch is None:
        xbmcplugin.endOfDirectory(HANDLE)
        return
    try:
        data = fetch(page)
    except Exception as e:
        error(f"TMDB error: {e}")
        xbmcplugin.endOfDirectory(HANDLE)
        return
    results: list[dict[str, Any]] = data.get("results", [])
    total_pages: int = data.get("total_pages", 1)
    next_url = (
        f"{_BASE}?category=shows&subcategory={subcategory}&page={page + 1}"
        if page < total_pages else ""
    )
    _render_shows(results, next_url)


def show_tv_genres():
    try:
        genres = Tmdb.tv_genres().get("genres", [])
    except Exception as e:
        error(f"TMDB error: {e}")
        xbmcplugin.endOfDirectory(HANDLE)
        return
    for genre in genres:
        li = xbmcgui.ListItem(label=genre["name"])
        url = (
            f"{_BASE}?category=shows&subcategory=genre"
            f"&genre_id={genre['id']}&genre_name={quote_plus(genre['name'])}"
        )
        _ = xbmcplugin.addDirectoryItem(HANDLE, url, li, isFolder=True)
    xbmcplugin.endOfDirectory(HANDLE)


def show_shows_by_genre(genre_id: int, genre_name: str = "", page: int = 1):
    try:
        data = Tmdb.tv_by_genre(genre_id, page)
    except Exception as e:
        error(f"TMDB error: {e}")
        xbmcplugin.endOfDirectory(HANDLE)
        return
    results: list[dict[str, Any]] = data.get("results", [])
    total_pages: int = data.get("total_pages", 1)
    next_url = (
        f"{_BASE}?category=shows&subcategory=genre&genre_id={genre_id}&genre_name={quote_plus(genre_name)}&page={page + 1}"
        if page < total_pages else ""
    )
    _render_shows(results, next_url)


def show_seasons(show_id: int, show_title: str = ""):
    try:
        details = Tmdb.tv_details(show_id)
    except Exception as e:
        error(f"TMDB error: {e}")
        xbmcplugin.endOfDirectory(HANDLE)
        return

    xbmcplugin.setContent(HANDLE, "tvshows")
    seasons: list[dict[str, Any]] = details.get("seasons", [])
    fanart = f"{_IMG}{details.get('backdrop_path')}" if details.get("backdrop_path") else ""

    for season in seasons:
        season_num = season.get("season_number", 0)
        episode_count = season.get("episode_count", 0)
        poster = season.get("poster_path") or ""
        name = season.get("name") or f"Season {season_num}"
        overview = season.get("overview", "")
        air_date = season.get("air_date", "")

        label = f"{name}  ({episode_count} episodes)"
        li = xbmcgui.ListItem(label=label)
        li.setInfo("video", {
            "title": label,
            "plot": overview,
            "season": season_num,
            "tvshowtitle": show_title,
            "aired": air_date,
            "mediatype": "season",
        })
        li.setArt({
            "thumb": f"{_IMG}{poster}" if poster else "",
            "poster": f"{_IMG}{poster}" if poster else "",
            "fanart": fanart,
        })
        url = (
            f"{_BASE}?action=episodes"
            f"&show_id={show_id}"
            f"&show_title={quote_plus(show_title)}"
            f"&season_number={season_num}"
        )
        _ = xbmcplugin.addDirectoryItem(HANDLE, url, li, isFolder=True)

    xbmcplugin.endOfDirectory(HANDLE)


def show_episodes(show_id: int, show_title: str, season_number: int):
    try:
        season = Tmdb.tv_season(show_id, season_number)
    except Exception as e:
        error(f"TMDB error: {e}")
        xbmcplugin.endOfDirectory(HANDLE)
        return

    xbmcplugin.setContent(HANDLE, "episodes")
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_EPISODE)
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_LABEL)

    season_poster = season.get("poster_path") or ""
    episodes: list[dict[str, Any]] = season.get("episodes", [])

    for ep in episodes:
        ep_num = ep.get("episode_number", 0)
        ep_name = ep.get("name", f"Episode {ep_num}")
        overview = ep.get("overview", "")
        still = ep.get("still_path") or ""
        rating = float(ep.get("vote_average") or 0)
        air_date = ep.get("air_date", "")

        label = f"{ep_num:02d}. {ep_name}"
        li = xbmcgui.ListItem(label=label)
        li.setProperty("IsPlayable", "true")
        li.setInfo("video", {
            "title": ep_name,
            "plot": overview,
            "season": season_number,
            "episode": ep_num,
            "tvshowtitle": show_title,
            "rating": rating,
            "aired": air_date,
            "mediatype": "episode",
        })
        li.setArt({
            "thumb": f"{_IMG}{still}" if still else f"{_IMG}{season_poster}" if season_poster else "",
            "poster": f"{_IMG}{season_poster}" if season_poster else "",
        })
        mw = (
            f"{_BASE}?action=trakt_mark_watched&type=episode"
            f"&id={show_id}&season={season_number}&episode={ep_num}"
        )
        li.addContextMenuItems([("Mark as Watched", f"RunPlugin({mw})")])
        url = (
            f"{_BASE}?action=play&type=episode"
            f"&id={show_id}"
            f"&season={season_number}"
            f"&episode={ep_num}"
        )
        _ = xbmcplugin.addDirectoryItem(HANDLE, url, li, isFolder=False)

    xbmcplugin.endOfDirectory(HANDLE)


def _render_shows(results: list[dict[str, Any]], next_url: str = ""):
    xbmcplugin.setContent(HANDLE, "tvshows")
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_LABEL)
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_VIDEO_RATING)
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_VIDEO_YEAR)

    for show in results:
        title = show.get("name", "Unknown")
        overview = show.get("overview", "")
        poster = show.get("poster_path") or ""
        backdrop = show.get("backdrop_path") or ""
        rating = float(show.get("vote_average") or 0)
        year_str = (show.get("first_air_date") or "")[:4]
        tmdb_id = int(show.get("id") or 0)
        genre_ids = [int(g) for g in show.get("genre_ids", [])]

        li = xbmcgui.ListItem(label=title)
        li.setInfo("video", {
            "title": title,
            "plot": overview,
            "year": int(year_str) if year_str.isdigit() else 0,
            "rating": rating,
            "genre": _genre_str(genre_ids),
            "mediatype": "tvshow",
        })
        li.setArt({
            "thumb": f"{_IMG}{poster}" if poster else "",
            "poster": f"{_IMG}{poster}" if poster else "",
            "fanart": f"{_IMG}{backdrop}" if backdrop else "",
        })
        li.addContextMenuItems(_menus("show", tmdb_id, title, year_str, poster))
        url = f"{_BASE}?action=seasons&show_id={tmdb_id}&show_title={quote_plus(title)}"
        _ = xbmcplugin.addDirectoryItem(HANDLE, url, li, isFolder=True)

    if next_url:
        li = xbmcgui.ListItem(label="Next Page →")
        _ = xbmcplugin.addDirectoryItem(HANDLE, next_url, li, isFolder=True)

    xbmcplugin.endOfDirectory(HANDLE)
