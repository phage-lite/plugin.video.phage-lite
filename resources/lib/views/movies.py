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
    ("Now Playing", "now_playing"),
    ("Top Rated", "top_rated"),
    ("Genres", "genres"),
]

_FETCHERS = {
    "popular": lambda: Tmdb.popular_movies()["results"],
    "trending": lambda: Tmdb.trending_movies()["results"],
    "now_playing": lambda: Tmdb.now_playing_movies()["results"],
    "top_rated": lambda: Tmdb.top_rated_movies()["results"],
}


def show_movie_categories():
    for label, key in _SUBCATEGORIES:
        li = xbmcgui.ListItem(label=label)
        url = f"{_BASE}?category=movies&subcategory={key}"
        xbmcplugin.addDirectoryItem(HANDLE, url, li, isFolder=True)
    xbmcplugin.endOfDirectory(HANDLE)


def show_movie_list(subcategory: str):
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
    _render_movies(results)


def show_movie_genres():
    try:
        genres = Tmdb.movie_genres().get("genres", [])
    except Exception as e:
        error(f"TMDB error: {e}")
        xbmcplugin.endOfDirectory(HANDLE)
        return
    for genre in genres:
        li = xbmcgui.ListItem(label=genre["name"])
        url = f"{_BASE}?category=movies&subcategory=genre&genre_id={genre['id']}&genre_name={quote_plus(genre['name'])}"
        xbmcplugin.addDirectoryItem(HANDLE, url, li, isFolder=True)
    xbmcplugin.endOfDirectory(HANDLE)


def show_movies_by_genre(genre_id: int, genre_name: str = ""):
    try:
        results = Tmdb.movies_by_genre(genre_id).get("results", [])
    except Exception as e:
        error(f"TMDB error: {e}")
        xbmcplugin.endOfDirectory(HANDLE)
        return
    _render_movies(results)


def _render_movies(results: list):
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
        url = f"{_BASE}?action=play&type=movie&id={tmdb_id}"
        xbmcplugin.addDirectoryItem(HANDLE, url, li, isFolder=False)

    xbmcplugin.endOfDirectory(HANDLE)
