import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable

import xbmcaddon
import xbmcgui
import xbmcplugin

from items import MovieItem
from services.tmdb import Tmdb
from utils.notifications import error
from utils.router import url

HANDLE = int(sys.argv[1])

_SUBCATEGORIES = [
    ("Popular", "popular", "popular"),
    ("Trending", "trending", "trending"),
    ("Now Playing", "now_playing", "intheatres"),
    ("Coming Soon", "upcoming", "calender"),
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
    "Action": "genre_action",
    "Adventure": "genre_adventure",
    "Animation": "genre_animation",
    "Comedy": "genre_comedy",
    "Crime": "genre_crime",
    "Documentary": "genre_documentary",
    "Drama": "genre_drama",
    "Family": "genre_family",
    "Fantasy": "genre_fantasy",
    "History": "genre_history",
    "Horror": "genre_horror",
    "Music": "genre_music",
    "Mystery": "genre_mystery",
    "Romance": "genre_romance",
    "Science Fiction": "genre_scifi",
    "Thriller": "genre_thriller",
    "TV Movie": "movies",
    "War": "genre_war",
    "Western": "genre_western",
}

_FETCHERS: dict[str, Callable[[int], dict[str, Any]]] = {
    "popular": lambda page: Tmdb.popular_movies(page),
    "trending": lambda page: Tmdb.trending_movies(page=page),
    "now_playing": lambda page: Tmdb.now_playing_movies(page),
    "upcoming": lambda page: Tmdb.upcoming_movies(page),
    "top_rated": lambda page: Tmdb.top_rated_movies(page),
}


def _menus(
    media_type: str, tmdb_id: int, title: str, year: str, poster: str
) -> list[tuple[str, str]]:
    fav = url("/favourite/add/", type=media_type, id=tmdb_id, title=title, year=year, poster=poster)
    wl = url("/trakt/watchlist/add/", type=media_type, id=tmdb_id)
    mw = url("/trakt/watched/", type=media_type, id=tmdb_id)
    ss = url("/play/select/", type=media_type, id=tmdb_id)
    sw_torrentio = url("/play/select/", type=media_type, id=tmdb_id, scraper="torrentio")
    sw_cocos = url("/play/select/", type=media_type, id=tmdb_id, scraper="cocoscrapers")
    return [
        ("Add to Favourites", f"RunPlugin({fav})"),
        ("Add to Trakt Watchlist", f"RunPlugin({wl})"),
        ("Mark as Watched", f"RunPlugin({mw})"),
        ("Select Source", f"PlayMedia({ss})"),
        ("Scrape with Torrentio", f"PlayMedia({sw_torrentio})"),
        ("Scrape with CocoScrapers", f"PlayMedia({sw_cocos})"),
    ]


def _dir_item(label: str, url: str, icon: str) -> None:
    li = xbmcgui.ListItem(label=label)
    icon_path = _icon(icon)
    li.setArt({"icon": icon_path, "thumb": icon_path, "poster": icon_path})
    _ = xbmcplugin.addDirectoryItem(HANDLE, url, li, isFolder=True)


def show_movie_categories():
    for label, key, icon in _SUBCATEGORIES:
        _dir_item(label, url(f"/movies/{key}/"), icon)

    _dir_item("My Favourites", url("/movies/favourites/"), "favorites")

    try:
        from services.trakt import Trakt

        if Trakt.is_authenticated:
            _dir_item("Because You Watched",   url("/movies/because_you_watched/"),   "because_you_watched")
            _dir_item("Because Most Watched",  url("/movies/because_most_watched/"),  "most_watched")
            _dir_item("Trakt Watchlist",       url("/movies/trakt_watchlist/"),       "trakt")
            _dir_item("Trakt Recommendations", url("/movies/trakt_recommendations/"), "because_you_watched")
    except Exception:
        pass

    xbmcplugin.endOfDirectory(HANDLE)


def _genre_map() -> dict[int, str]:
    try:
        genres = Tmdb.movie_genres().get("genres", [])
        return {int(g["id"]): str(g["name"]) for g in genres}
    except Exception:
        return {}


def show_movie_list(subcategory: str, page: int = 1):
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
    next_url = url(f"/movies/{subcategory}/", page=page + 1) if page < total_pages else ""
    _render_movies(results, next_url)


def show_movie_genres():
    try:
        genres = Tmdb.movie_genres().get("genres", [])
    except Exception as e:
        error(f"TMDB error: {e}")
        xbmcplugin.endOfDirectory(HANDLE)
        return
    for genre in genres:
        name = genre["name"]
        genre_url = url("/movies/genre/:genre_id/", genre_id=genre["id"], genre_name=name)
        _dir_item(name, genre_url, _GENRE_ICONS.get(name, "genres"))
    xbmcplugin.endOfDirectory(HANDLE)


def show_movies_by_genre(genre_id: int, genre_name: str = "", page: int = 1):
    try:
        data = Tmdb.movies_by_genre(genre_id, page)
    except Exception as e:
        error(f"TMDB error: {e}")
        xbmcplugin.endOfDirectory(HANDLE)
        return
    results: list[dict[str, Any]] = data.get("results", [])
    total_pages: int = data.get("total_pages", 1)
    next_url = (
        url("/movies/genre/:genre_id/", genre_id=genre_id, genre_name=genre_name, page=page + 1)
        if page < total_pages else ""
    )
    _render_movies(results, next_url)


def _fetch_movie_details(movie: dict[str, Any]) -> dict[str, Any]:
    tmdb_id = int(movie.get("id") or 0)
    if not tmdb_id:
        return movie
    try:
        return Tmdb.movie_rich_details(tmdb_id)
    except Exception:
        return movie


def _render_movies(
    results: list[dict[str, Any]],
    next_url: str = "",
):
    xbmcplugin.setContent(HANDLE, "movies")
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_LABEL)
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_VIDEO_RATING)
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_VIDEO_YEAR)

    with ThreadPoolExecutor(max_workers=5) as executor:
        future_to_movie = {
            executor.submit(_fetch_movie_details, movie): movie for movie in results
        }
        details_map: dict[int, dict[str, Any]] = {}
        for future in as_completed(future_to_movie):
            original = future_to_movie[future]
            movie_id = int(original.get("id") or 0)
            try:
                details_map[movie_id] = future.result()
            except Exception:
                details_map[movie_id] = original

    for movie in results:
        tmdb_id = int(movie.get("id") or 0)
        details = details_map.get(tmdb_id, movie)
        title = details.get("title") or movie.get("title") or "Unknown"
        year_str = (details.get("release_date") or movie.get("release_date") or "")[:4]
        poster_path = details.get("poster_path") or movie.get("poster_path") or ""

        item = MovieItem(details)
        li = item.build()
        li.addContextMenuItems(_menus("movie", tmdb_id, title, year_str, poster_path))
        _ = xbmcplugin.addDirectoryItem(HANDLE, url("/play/", type="movie", id=tmdb_id), li, isFolder=False)

    if next_url:
        li = xbmcgui.ListItem(label="Next Page →")
        li.setProperty("SpecialSort", "bottom")
        p = _icon("nextpage")
        li.setArt({"icon": p, "thumb": p, "poster": p})
        _ = xbmcplugin.addDirectoryItem(HANDLE, next_url, li, isFolder=True)

    xbmcplugin.endOfDirectory(HANDLE)
