import os
import sys
import xbmcaddon
import xbmcgui
import xbmcplugin
from typing import Any, Callable
from urllib.parse import quote_plus

from services.tmdb import Tmdb
from settings.settings import get_setting
from utils.notifications import error

HANDLE = int(sys.argv[1])
_BASE = sys.argv[0]
_IMG = "https://image.tmdb.org/t/p/w500"

_SUBCATEGORIES = [
    ("Popular",     "popular",     "popular"),
    ("Trending",    "trending",    "trending"),
    ("Now Playing", "now_playing", "intheatres"),
    ("Coming Soon", "upcoming",    "calender"),
    ("Top Rated",   "top_rated",   "top"),
    ("Genres",      "genres",      "genres"),
]

def _icon(name: str) -> str:
    return os.path.join(xbmcaddon.Addon().getAddonInfo("path"), "resources", "media", "icons", name + ".png")


_GENRE_ICONS: dict[str, str] = {
    "Action":          "genre_action",
    "Adventure":       "genre_adventure",
    "Animation":       "genre_animation",
    "Comedy":          "genre_comedy",
    "Crime":           "genre_crime",
    "Documentary":     "genre_documentary",
    "Drama":           "genre_drama",
    "Family":          "genre_family",
    "Fantasy":         "genre_fantasy",
    "History":         "genre_history",
    "Horror":          "genre_horror",
    "Music":           "genre_music",
    "Mystery":         "genre_mystery",
    "Romance":         "genre_romance",
    "Science Fiction": "genre_scifi",
    "Thriller":        "genre_thriller",
    "TV Movie":        "movies",
    "War":             "genre_war",
    "Western":         "genre_western",
}

_FETCHERS: dict[str, Callable[[int], dict[str, Any]]] = {
    "popular":     lambda page: Tmdb.popular_movies(page),
    "trending":    lambda page: Tmdb.trending_movies(page=page),
    "now_playing": lambda page: Tmdb.now_playing_movies(page),
    "upcoming":    lambda page: Tmdb.upcoming_movies(page),
    "top_rated":   lambda page: Tmdb.top_rated_movies(page),
    "adult":       lambda page: Tmdb.adult_movies(page),
}


def _adult_enabled() -> bool:
    import xbmcaddon
    return xbmcaddon.Addon().getSetting("tmdb.include_adult") == "true"


def _menus(media_type: str, tmdb_id: int, title: str, year: str, poster: str) -> list[tuple[str, str]]:
    fav = (
        f"{_BASE}?action=favourite_add&type={media_type}&id={tmdb_id}"
        f"&title={quote_plus(title)}&year={year}&poster={quote_plus(poster)}"
    )
    wl = f"{_BASE}?action=trakt_watchlist_add&type={media_type}&id={tmdb_id}"
    mw = f"{_BASE}?action=trakt_mark_watched&type={media_type}&id={tmdb_id}"
    return [
        ("Add to Favourites", f"RunPlugin({fav})"),
        ("Add to Trakt Watchlist", f"RunPlugin({wl})"),
        ("Mark as Watched", f"RunPlugin({mw})"),
    ]


def _dir_item(label: str, url: str, icon: str) -> None:
    li = xbmcgui.ListItem(label=label)
    icon_path = _icon(icon)
    li.setArt({"icon": icon_path, "thumb": icon_path, "poster": icon_path})
    _ = xbmcplugin.addDirectoryItem(HANDLE, url, li, isFolder=True)


def show_movie_categories():
    for label, key, icon in _SUBCATEGORIES:
        _dir_item(label, f"{_BASE}?category=movies&subcategory={key}", icon)

    _dir_item("My Favourites", f"{_BASE}?category=movies&subcategory=favourites", "favorites")

    try:
        from services.trakt import Trakt
        if Trakt.is_authenticated():
            _dir_item("Trakt Watchlist", f"{_BASE}?category=movies&subcategory=trakt_watchlist", "trakt")
            _dir_item("Trakt Recommendations", f"{_BASE}?category=movies&subcategory=trakt_recommendations", "because_you_watched")
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
    next_url = (
        f"{_BASE}?category=movies&subcategory={subcategory}&page={page + 1}"
        if page < total_pages else ""
    )
    _render_movies(results, next_url, _genre_map())


def show_movie_genres():
    try:
        genres = Tmdb.movie_genres().get("genres", [])
    except Exception as e:
        error(f"TMDB error: {e}")
        xbmcplugin.endOfDirectory(HANDLE)
        return
    for genre in genres:
        name = genre["name"]
        url = (
            f"{_BASE}?category=movies&subcategory=genre"
            f"&genre_id={genre['id']}&genre_name={quote_plus(name)}"
        )
        _dir_item(name, url, _GENRE_ICONS.get(name, "genres"))
    if _adult_enabled():
        _dir_item("Adult", f"{_BASE}?category=movies&subcategory=adult", "sex_nudity")
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
        f"{_BASE}?category=movies&subcategory=genre&genre_id={genre_id}&genre_name={quote_plus(genre_name)}&page={page + 1}"
        if page < total_pages else ""
    )
    _render_movies(results, next_url, _genre_map())


def _render_movies(results: list[dict[str, Any]], next_url: str = "", genre_map: dict[int, str] | None = None):
    gmap = genre_map or {}
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
        tmdb_id = int(movie.get("id") or 0)
        genre_ids = [int(g) for g in movie.get("genre_ids", [])]
        genre_str = " / ".join(gmap[g] for g in genre_ids[:3] if g in gmap)

        li = xbmcgui.ListItem(label=title)
        li.setProperty("IsPlayable", "true")
        li.setInfo("video", {
            "title": title,
            "plot": overview,
            "year": int(year_str) if year_str.isdigit() else 0,
            "rating": rating,
            "genre": genre_str,
            "mediatype": "movie",
        })
        li.setArt({
            "thumb": f"{_IMG}{poster}" if poster else "",
            "poster": f"{_IMG}{poster}" if poster else "",
            "fanart": f"{_IMG}{backdrop}" if backdrop else "",
        })
        li.addContextMenuItems(_menus("movie", tmdb_id, title, year_str, poster))
        _ = xbmcplugin.addDirectoryItem(
            HANDLE, f"{_BASE}?action=play&type=movie&id={tmdb_id}", li, isFolder=False
        )

    if next_url:
        li = xbmcgui.ListItem(label="Next Page →")
        li.setProperty("SpecialSort", "bottom")
        p = _icon("nextpage")
        li.setArt({"icon": p, "thumb": p, "poster": p})
        _ = xbmcplugin.addDirectoryItem(HANDLE, next_url, li, isFolder=True)

    xbmcplugin.endOfDirectory(HANDLE)
