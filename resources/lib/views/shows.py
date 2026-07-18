import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable

import xbmcaddon
import xbmcgui
import xbmcplugin

from menu_items.episode import EpisodeItem
from menu_items.season import SeasonItem
from menu_items.show import ShowItem
from services.tmdb import Tmdb
from utils.logger import debug, log
from utils.notifications import error
from utils.router import url

HANDLE = int(sys.argv[1])

_SUBCATEGORIES = [
    ("Next Up", "upnext", "next_episodes"),
    ("In Progress Shows", "in_progress", "in_progress_tvshow"),
    ("Popular", "popular", "popular"),
    ("Trending", "trending", "trending"),
    ("Watchlist", "watchlist", "trakt"),
    ("My Favourites", "favourites", "favourites"),
    ("My Calendar", "calendar", "calendar"),
    ("Recommended", "recommended", "discover"),
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


def _dir_item(label: str, url: str, icon: str) -> None:
    li = xbmcgui.ListItem(label=label)
    icon_path = _icon(icon)
    li.setArt({"icon": icon_path, "thumb": icon_path, "poster": icon_path})
    _ = xbmcplugin.addDirectoryItem(HANDLE, url, li, isFolder=True)


def show_tv_categories():
    for label, key, icon in _SUBCATEGORIES:
        _dir_item(label, url(f"/shows/{key}/"), icon)

    xbmcplugin.endOfDirectory(HANDLE)


def show_tv_list(subcategory: str, page: int = 1):
    fetch = _FETCHERS.get(subcategory)
    if fetch is None:
        xbmcplugin.endOfDirectory(HANDLE)
        return
    try:
        data = fetch(page)
    except Exception as e:
        error(f"Fetcher error: {e}")
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


def show_seasons(show_id: int):
    try:
        show_details = Tmdb.tv_show_details(show_id)
    except Exception as e:
        error(f"TMDB error: {e}")
        xbmcplugin.endOfDirectory(HANDLE)
        return
    debug(f"{show_id}", "show_id")

    xbmcplugin.setContent(HANDLE, "tvshows")
    seasons: list[dict[str, Any]] = show_details.get("seasons", [])
    show_art = ShowItem.extract_art(show_details)

    for season in seasons:
        item = SeasonItem(season, show_details, show_art)
        _ = xbmcplugin.addDirectoryItem(HANDLE, item.url, item.listItem, isFolder=True)

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

        _ = xbmcplugin.addDirectoryItem(HANDLE, item.url, item.listItem)

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
        item = ShowItem(details)
        _ = xbmcplugin.addDirectoryItem(HANDLE, item.url, item.listItem, isFolder=True)

    if next_url:
        li = xbmcgui.ListItem(label="Next Page")
        li.setProperty("SpecialSort", "bottom")
        p = _icon("nextpage")
        li.setArt({"icon": p, "thumb": p, "poster": p})
        _ = xbmcplugin.addDirectoryItem(HANDLE, next_url, li, isFolder=True)

    xbmcplugin.endOfDirectory(HANDLE)
