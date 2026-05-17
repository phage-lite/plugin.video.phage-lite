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
    ("Now Playing", "now_playing"),
    ("Top Rated", "top_rated"),
    ("Genres", "genres"),
]

_FETCHERS: dict[str, Callable[[int], dict[str, Any]]] = {
    "popular":    lambda page: Tmdb.popular_movies(page),
    "trending":   lambda page: Tmdb.trending_movies(page=page),
    "now_playing": lambda page: Tmdb.now_playing_movies(page),
    "top_rated":  lambda page: Tmdb.top_rated_movies(page),
    "adult":      lambda page: Tmdb.adult_movies(page),
}


def show_movie_categories():
    for label, key in _SUBCATEGORIES:
        li = xbmcgui.ListItem(label=label)
        xbmcplugin.addDirectoryItem(HANDLE, f"{_BASE}?category=movies&subcategory={key}", li, isFolder=True)
    xbmcplugin.endOfDirectory(HANDLE)


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
    next_url = (
        f"{_BASE}?category=movies&subcategory={subcategory}&page={page + 1}"
        if page < total_pages else ""
    )
    _render_movies(results, next_url)


def show_movie_genres():
    try:
        genres = Tmdb.movie_genres().get("genres", [])
    except Exception as e:
        error(f"TMDB error: {e}")
        xbmcplugin.endOfDirectory(HANDLE)
        return
    for genre in genres:
        li = xbmcgui.ListItem(label=genre["name"])
        url = (
            f"{_BASE}?category=movies&subcategory=genre"
            f"&genre_id={genre['id']}&genre_name={quote_plus(genre['name'])}"
        )
        xbmcplugin.addDirectoryItem(HANDLE, url, li, isFolder=True)
    li = xbmcgui.ListItem(label="Adult")
    xbmcplugin.addDirectoryItem(HANDLE, f"{_BASE}?category=movies&subcategory=adult", li, isFolder=True)
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
        f"{_BASE}?category=movies&subcategory=genre"
        f"&genre_id={genre_id}&genre_name={quote_plus(genre_name)}&page={page + 1}"
        if page < total_pages else ""
    )
    _render_movies(results, next_url)


def _render_movies(results: list[dict[str, Any]], next_url: str = ""):
    xbmcplugin.setContent(HANDLE, "movies")
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_LABEL)
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_VIDEO_RATING)
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_VIDEO_YEAR)

    for movie in results:
        title = movie.get("title", "Unknown")
        overview = movie.get("overview", "")
        poster = movie.get("poster_path") or ""
        backdrop = movie.get("backdrop_path") or ""
        rating = float(movie.get("vote_average") or 0)
        year_str = (movie.get("release_date") or "")[:4]
        tmdb_id = movie.get("id")

        li = xbmcgui.ListItem(label=title)
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

    if next_url:
        li = xbmcgui.ListItem(label="Next Page →")
        xbmcplugin.addDirectoryItem(HANDLE, next_url, li, isFolder=True)

    xbmcplugin.endOfDirectory(HANDLE)
