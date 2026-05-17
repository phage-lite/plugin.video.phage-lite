import sys
import xbmcgui
import xbmcplugin
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
    ("Top Rated", "top_rated"),
    ("Genres", "genres"),
]

_FETCHERS = {
    "popular": lambda: Tmdb.popular_tv()["results"],
    "trending": lambda: Tmdb.trending_tv()["results"],
    "airing_today": lambda: Tmdb.airing_today_tv()["results"],
    "top_rated": lambda: Tmdb.top_rated_tv()["results"],
}


def show_tv_categories():
    for label, key in _SUBCATEGORIES:
        li = xbmcgui.ListItem(label=label)
        url = f"{_BASE}?category=shows&subcategory={key}"
        xbmcplugin.addDirectoryItem(HANDLE, url, li, isFolder=True)
    xbmcplugin.endOfDirectory(HANDLE)


def show_tv_list(subcategory: str):
    fetch = _FETCHERS.get(subcategory)
    if fetch is None:
        xbmcplugin.endOfDirectory(HANDLE)
        return
    try:
        results = fetch()
    except Exception as e:
        error(f"TMDB error: {e}")
        xbmcplugin.endOfDirectory(HANDLE)
        return
    _render_shows(results)


def show_tv_genres():
    try:
        genres = Tmdb.tv_genres().get("genres", [])
    except Exception as e:
        error(f"TMDB error: {e}")
        xbmcplugin.endOfDirectory(HANDLE)
        return
    for genre in genres:
        li = xbmcgui.ListItem(label=genre["name"])
        url = f"{_BASE}?category=shows&subcategory=genre&genre_id={genre['id']}&genre_name={quote_plus(genre['name'])}"
        xbmcplugin.addDirectoryItem(HANDLE, url, li, isFolder=True)
    xbmcplugin.endOfDirectory(HANDLE)


def show_shows_by_genre(genre_id: int, genre_name: str = ""):
    try:
        results = Tmdb.tv_by_genre(genre_id).get("results", [])
    except Exception as e:
        error(f"TMDB error: {e}")
        xbmcplugin.endOfDirectory(HANDLE)
        return
    _render_shows(results)


def show_seasons(show_id: int, show_title: str = ""):
    try:
        details = Tmdb.tv_details(show_id)
    except Exception as e:
        error(f"TMDB error: {e}")
        xbmcplugin.endOfDirectory(HANDLE)
        return

    xbmcplugin.setContent(HANDLE, "tvshows")
    seasons = details.get("seasons", [])
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
        xbmcplugin.addDirectoryItem(HANDLE, url, li, isFolder=True)

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
    episodes = season.get("episodes", [])

    for ep in episodes:
        ep_num = ep.get("episode_number", 0)
        ep_name = ep.get("name", f"Episode {ep_num}")
        overview = ep.get("overview", "")
        still = ep.get("still_path") or ""
        rating = float(ep.get("vote_average") or 0)
        air_date = ep.get("air_date", "")

        label = f"{ep_num:02d}. {ep_name}"
        li = xbmcgui.ListItem(label=label)
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
        url = (
            f"{_BASE}?action=play&type=episode"
            f"&id={show_id}"
            f"&season={season_number}"
            f"&episode={ep_num}"
        )
        xbmcplugin.addDirectoryItem(HANDLE, url, li, isFolder=False)

    xbmcplugin.endOfDirectory(HANDLE)


def _render_shows(results: list):
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
        tmdb_id = show.get("id")

        li = xbmcgui.ListItem(label=title)
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
        url = (
            f"{_BASE}?action=seasons"
            f"&show_id={tmdb_id}"
            f"&show_title={quote_plus(title)}"
        )
        xbmcplugin.addDirectoryItem(HANDLE, url, li, isFolder=True)

    xbmcplugin.endOfDirectory(HANDLE)
