import os
import sys
import xbmcaddon
import xbmcgui
import xbmcplugin
from typing import Any, Callable

from services.tmdb import Tmdb
from utils.notifications import error
from utils.router import url

HANDLE = int(sys.argv[1])
_IMG = "https://image.tmdb.org/t/p/w500"

_SUBCATEGORIES = [
    ("Popular",          "popular",     "popular"),
    ("Trending",         "trending",    "trending"),
    ("Airing Today",     "airing_today","airing"),
    ("On Air This Week", "on_air",      "ontheair"),
    ("Top Rated",        "top_rated",   "top"),
    ("Genres",           "genres",      "genres"),
]

def _icon(name: str) -> str:
    return os.path.join(xbmcaddon.Addon().getAddonInfo("path"), "resources", "media", "icons", name + ".png")


_GENRE_ICONS: dict[str, str] = {
    "Action & Adventure": "genre_action",
    "Animation":          "genre_animation",
    "Comedy":             "genre_comedy",
    "Crime":              "genre_crime",
    "Documentary":        "genre_documentary",
    "Drama":              "genre_drama",
    "Family":             "genre_family",
    "Kids":               "genre_kids",
    "Mystery":            "genre_mystery",
    "News":               "genre_news",
    "Reality":            "genre_reality",
    "Sci-Fi & Fantasy":   "genre_scifi",
    "Soap":               "genre_soap",
    "Talk":               "genre_talk",
    "War & Politics":     "genre_war",
    "Western":            "genre_western",
}

_FETCHERS: dict[str, Callable[[int], dict[str, Any]]] = {
    "popular":      lambda page: Tmdb.popular_tv(page),
    "trending":     lambda page: Tmdb.trending_tv(page=page),
    "airing_today": lambda page: Tmdb.airing_today_tv(page),
    "on_air":       lambda page: Tmdb.on_air_tv(page),
    "top_rated":    lambda page: Tmdb.top_rated_tv(page),
}


def _menus(media_type: str, tmdb_id: int, title: str, year: str, poster: str) -> list[tuple[str, str]]:
    fav = url("/favourite/add/", type=media_type, id=tmdb_id, title=title, year=year, poster=poster)
    wl = url("/trakt/watchlist/add/", type=media_type, id=tmdb_id)
    return [
        ("Add to Favourites", f"RunPlugin({fav})"),
        ("Add to Trakt Watchlist", f"RunPlugin({wl})"),
    ]


def _dir_item(label: str, url: str, icon: str) -> None:
    li = xbmcgui.ListItem(label=label)
    icon_path = _icon(icon)
    li.setArt({"icon": icon_path, "thumb": icon_path, "poster": icon_path})
    _ = xbmcplugin.addDirectoryItem(HANDLE, url, li, isFolder=True)


def show_tv_categories():
    for label, key, icon in _SUBCATEGORIES:
        _dir_item(label, url(f"/shows/{key}/"), icon)

    _dir_item("My Favourites", url("/shows/favourites/"), "favorites")

    try:
        from services.trakt import Trakt
        if Trakt.is_authenticated:
            _dir_item("Up Next",               url("/shows/upnext/"),               "next_episodes")
            _dir_item("In Progress",           url("/shows/in_progress/"),           "in_progress_tvshow")
            _dir_item("Because You Watched",   url("/shows/because_you_watched/"),   "because_you_watched")
            _dir_item("Because Most Watched",  url("/shows/because_most_watched/"),  "most_watched")
            _dir_item("Trakt Watchlist",       url("/shows/trakt_watchlist/"),       "trakt")
            _dir_item("Trakt Recommendations", url("/shows/trakt_recommendations/"), "because_you_watched")
            _dir_item("My Calendar",           url("/shows/calendar/"),              "calender")
    except Exception:
        pass

    xbmcplugin.endOfDirectory(HANDLE)


def _genre_map() -> dict[int, str]:
    try:
        genres = Tmdb.tv_genres().get("genres", [])
        return {int(g["id"]): str(g["name"]) for g in genres}
    except Exception:
        return {}


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
    next_url = url(f"/shows/{subcategory}/", page=page + 1) if page < total_pages else ""
    _render_shows(results, next_url, _genre_map())


def show_tv_genres():
    try:
        genres = Tmdb.tv_genres().get("genres", [])
    except Exception as e:
        error(f"TMDB error: {e}")
        xbmcplugin.endOfDirectory(HANDLE)
        return
    for genre in genres:
        name = genre["name"]
        genre_url = url("/shows/genre/:genre_id/", genre_id=genre["id"], genre_name=name)
        _dir_item(name, genre_url, _GENRE_ICONS.get(name, "genres"))
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
        url("/shows/genre/:genre_id/", genre_id=genre_id, genre_name=genre_name, page=page + 1)
        if page < total_pages else ""
    )
    _render_shows(results, next_url, _genre_map())


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
        ep_url = url(
            "/show/:show_id/season/:season_number/episodes/",
            show_id=show_id, season_number=season_num, show_title=show_title,
        )
        _ = xbmcplugin.addDirectoryItem(HANDLE, ep_url, li, isFolder=True)

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
        mw = url("/trakt/watched/", type="episode", id=show_id, season=season_number, episode=ep_num)
        ss = url("/play/select/", type="episode", id=show_id, season=season_number, episode=ep_num)
        sw_torrentio = url("/play/select/", type="episode", id=show_id, season=season_number, episode=ep_num, scraper="torrentio")
        sw_cocos = url("/play/select/", type="episode", id=show_id, season=season_number, episode=ep_num, scraper="cocoscrapers")
        li.addContextMenuItems([
            ("Mark as Watched", f"RunPlugin({mw})"),
            ("Select Source", f"PlayMedia({ss})"),
            ("Scrape with Torrentio", f"PlayMedia({sw_torrentio})"),
            ("Scrape with CocoScrapers", f"PlayMedia({sw_cocos})"),
        ])
        play_url = url("/play/", type="episode", id=show_id, season=season_number, episode=ep_num)
        _ = xbmcplugin.addDirectoryItem(HANDLE, play_url, li, isFolder=False)

    xbmcplugin.endOfDirectory(HANDLE)


def _render_shows(results: list[dict[str, Any]], next_url: str = "", genre_map: dict[int, str] | None = None):
    gmap = genre_map or {}
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
        genre_str = " / ".join(gmap[g] for g in genre_ids[:3] if g in gmap)

        li = xbmcgui.ListItem(label=title)
        li.setInfo("video", {
            "title": title,
            "plot": overview,
            "year": int(year_str) if year_str.isdigit() else 0,
            "rating": rating,
            "genre": genre_str,
            "mediatype": "tvshow",
        })
        li.setArt({
            "thumb": f"{_IMG}{poster}" if poster else "",
            "poster": f"{_IMG}{poster}" if poster else "",
            "fanart": f"{_IMG}{backdrop}" if backdrop else "",
        })
        li.addContextMenuItems(_menus("show", tmdb_id, title, year_str, poster))
        show_url = url("/show/:show_id/seasons/", show_id=tmdb_id, show_title=title)
        _ = xbmcplugin.addDirectoryItem(HANDLE, show_url, li, isFolder=True)

    if next_url:
        li = xbmcgui.ListItem(label="Next Page →")
        li.setProperty("SpecialSort", "bottom")
        p = _icon("nextpage")
        li.setArt({"icon": p, "thumb": p, "poster": p})
        _ = xbmcplugin.addDirectoryItem(HANDLE, next_url, li, isFolder=True)

    xbmcplugin.endOfDirectory(HANDLE)
