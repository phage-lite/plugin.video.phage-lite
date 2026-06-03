import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable

import xbmcaddon
import xbmcgui
import xbmcplugin

from items import EpisodeItem, SeasonItem, ShowItem
from services.tmdb import Tmdb
from utils.logger import log
from utils.notifications import error
from utils.router import url

HANDLE = int(sys.argv[1])

_SUBCATEGORIES = [
    ("Next Up", "upnext", "next_episodes"),
    ("In Progress Shows", "in_progress", "in_progress_tvshow"),
    ("Popular", "popular", "popular"),
    ("Trending", "trending", "trending"),
    ("Watchlist", "trakt_watchlist", "trakt"),
    ("My Favourites", "favourites", "favorites"),
    ("My Calendar", "calendar", "calendar"),
    ("Recommendations", "trakt_recommendations", "discover"),
    ("Because You Watched", "because_you_watched", "because_you_watched"),
    ("Because Others Watched", "because_most_watched", "most_watched"),
    ("Airing Today", "airing_today", "airing"),
    ("On Air This Week", "on_air", "ontheair"),
    ("Top Rated", "top_rated", "top"),
    ("Genres", "genres", "genres"),
]


def _icon(name: str) -> str:
    return os.path.join(
        xbmcaddon.Addon().getAddonInfo("path"),
        "resources",
        "media",
        "icons",
        name + ".png",
    )


_GENRE_ICONS: dict[str, str] = {
    "Action & Adventure": "genre_action",
    "Animation": "genre_animation",
    "Comedy": "genre_comedy",
    "Crime": "genre_crime",
    "Documentary": "genre_documentary",
    "Drama": "genre_drama",
    "Family": "genre_family",
    "Kids": "genre_kids",
    "Mystery": "genre_mystery",
    "News": "genre_news",
    "Reality": "genre_reality",
    "Sci-Fi & Fantasy": "genre_scifi",
    "Soap": "genre_soap",
    "Talk": "genre_talk",
    "War & Politics": "genre_war",
    "Western": "genre_western",
}

_FETCHERS: dict[str, Callable[[int], dict[str, Any]]] = {
    "popular": lambda page: Tmdb.popular_tv(page),
    "trending": lambda page: Tmdb.trending_tv(page=page),
    "airing_today": lambda page: Tmdb.airing_today_tv(page),
    "on_air": lambda page: Tmdb.on_air_tv(page),
    "top_rated": lambda page: Tmdb.top_rated_tv(page),
}


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


def _dir_item(label: str, url: str, icon: str) -> None:
    li = xbmcgui.ListItem(label=label)
    icon_path = _icon(icon)
    li.setArt({"icon": icon_path, "thumb": icon_path, "poster": icon_path})
    _ = xbmcplugin.addDirectoryItem(HANDLE, url, li, isFolder=True)


def show_tv_categories():
    for label, key, icon in _SUBCATEGORIES:
        _dir_item(label, url(f"/shows/{key}/"), icon)

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
    next_url = (
        url(f"/shows/{subcategory}/", page=page + 1) if page < total_pages else ""
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
        name = genre["name"]
        genre_url = url(
            "/shows/genre/:genre_id/", genre_id=genre["id"], genre_name=name
        )
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
        url(
            "/shows/genre/:genre_id/",
            genre_id=genre_id,
            genre_name=genre_name,
            page=page + 1,
        )
        if page < total_pages
        else ""
    )
    _render_shows(results, next_url)


def show_seasons(show_id: int, show_title: str = ""):
    try:
        details = Tmdb.tv_show_details(show_id)
    except Exception as e:
        error(f"TMDB error: {e}")
        xbmcplugin.endOfDirectory(HANDLE)
        return
    log(f"{show_id}", "show_id")

    xbmcplugin.setContent(HANDLE, "tvshows")
    seasons: list[dict[str, Any]] = details.get("seasons", [])
    show_art = ShowItem.extract_art(details)

    for season in seasons:
        log(f"{season}", "season")
        item = SeasonItem(season, show_title, show_art)
        li = item.build()
        season_num = season.get("season_number", 0)
        ep_url = url(
            "/show/:show_id/season/:season_number/episodes/",
            show_id=show_id,
            season_number=season_num,
            show_title=show_title,
        )
        _ = xbmcplugin.addDirectoryItem(HANDLE, ep_url, li, isFolder=True)

    xbmcplugin.endOfDirectory(HANDLE)


def show_episodes(show_id: int, season_number: int):
    try:
        season_details = Tmdb.tv_season(show_id, season_number)
        show_details = Tmdb.tv_show_details(show_id)
    except Exception as e:
        error(f"TMDB error: {e}")
        xbmcplugin.endOfDirectory(HANDLE)
        return

    xbmcplugin.setContent(HANDLE, "episodes")
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_EPISODE)
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_LABEL)

    episodes: list[dict[str, Any]] = season_details.get("episodes", [])

    for ep in episodes:
        ep_num = ep.get("episode_number", 0)
        item = EpisodeItem(ep_num, season_details, show_details)
        li = item.build()

        _ = xbmcplugin.addDirectoryItem(HANDLE, item.play_url, li)

    xbmcplugin.endOfDirectory(HANDLE)


def _fetch_show_details(show: dict[str, Any]) -> dict[str, Any]:
    tmdb_id = int(show.get("id") or 0)
    if not tmdb_id:
        return show
    try:
        return Tmdb.tv_show_details(tmdb_id)
    except Exception:
        return show


def _render_shows(
    results: list[dict[str, Any]],
    next_url: str = "",
):
    xbmcplugin.setContent(HANDLE, "tvshows")
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_LABEL)
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_VIDEO_RATING)
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_VIDEO_YEAR)

    with ThreadPoolExecutor(max_workers=5) as executor:
        future_to_show = {
            executor.submit(_fetch_show_details, show): show for show in results
        }
        details_map: dict[int, dict[str, Any]] = {}
        for future in as_completed(future_to_show):
            original = future_to_show[future]
            show_id = int(original.get("id") or 0)
            try:
                details_map[show_id] = future.result()
            except Exception:
                details_map[show_id] = original

    for show in results:
        tmdb_id = int(show.get("id") or 0)
        details = details_map.get(tmdb_id, show)
        title = details.get("name") or show.get("name") or "Unknown"
        year_str = (details.get("first_air_date") or show.get("first_air_date") or "")[
            :4
        ]
        poster_path = details.get("poster_path") or show.get("poster_path") or ""

        item = ShowItem(details)
        li = item.build()
        li.addContextMenuItems(_menus("show", tmdb_id, title, year_str, poster_path))
        show_url = url("/show/:show_id/seasons/", show_id=tmdb_id, show_title=title)
        _ = xbmcplugin.addDirectoryItem(HANDLE, show_url, li, isFolder=True)

    if next_url:
        li = xbmcgui.ListItem(label="Next Page →")
        li.setProperty("SpecialSort", "bottom")
        p = _icon("nextpage")
        li.setArt({"icon": p, "thumb": p, "poster": p})
        _ = xbmcplugin.addDirectoryItem(HANDLE, next_url, li, isFolder=True)

    xbmcplugin.endOfDirectory(HANDLE)
