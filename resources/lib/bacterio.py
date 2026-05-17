import sys
import xbmcgui
import xbmcplugin
import xbmcaddon

from urllib.parse import parse_qsl
from utils.notifications import error
from services.tmdb import Tmdb

HANDLE = int(sys.argv[1])

CATEGORIES = [
    ("Movies", "movies"),
    ("Shows", "shows"),
    ("Settings", "settings"),
]

MOVIE_CATEGORIES = [
    ("Popular", "popular"),
    ("Trending", "trending"),
    ("Now Playing", "now_playing"),
    ("Top Rated", "top_rated"),
    ("Genres", "genres"),
]


def get_params():
    return dict(parse_qsl(sys.argv[2].lstrip("?")))


def show_home():
    for label, key in CATEGORIES:
        li = xbmcgui.ListItem(label=label)
        url = f"{sys.argv[0]}?category={key}"
        success = xbmcplugin.addDirectoryItem(HANDLE, url, li, isFolder=True)
        if not success:
            error(f"Error building home page entry for: {key}")
    xbmcplugin.endOfDirectory(HANDLE)


def show_movies():
    for label, key in MOVIE_CATEGORIES:
        li = xbmcgui.ListItem(label=label)
        url = f"{sys.argv[0]}?category=movies&subcategory={key}"
        success = xbmcplugin.addDirectoryItem(HANDLE, url, li, isFolder=True)
        if not success:
            error(f"Error adding movie subcategory: {key}")
    xbmcplugin.endOfDirectory(HANDLE)


def show_movie_list(subcategory: str):
    if subcategory == "popular":
        results = Tmdb.popular_movies()["results"]
    elif subcategory == "trending":
        results = Tmdb.trending_movies()["results"]
    elif subcategory == "now_playing":
        results = Tmdb.now_playing_movies()["results"]
    elif subcategory == "top_rated":
        results = Tmdb.top_rated_movies()["results"]
    else:
        return

    for movie in results:
        title = movie["title"]
        year = movie.get("release_date", "")[:4]
        rating = movie.get("vote_average", 0)
        label = f"{title} ({year}) [{rating}]"
        li = xbmcgui.ListItem(label=label)
        url = f"{sys.argv[0]}?action=play&type=movie&id={movie['id']}"
        success = xbmcplugin.addDirectoryItem(HANDLE, url, li, isFolder=False)
        if not success:
            error(f"Error adding movie item: {title}")

    xbmcplugin.endOfDirectory(HANDLE)


def play_movie(_: str):
    error("Not implemented")


def show_tv_shows():
    error("Not implemented")


if __name__ == "__main__":
    params = get_params()
    category = params.get("category")
    subcategory = params.get("subcategory")
    action = params.get("action")

    if action == "play":
        id = params.get("id")
        if id:
            play_movie(id)
    elif not category:
        show_home()
    elif category == "movies":
        if subcategory:
            show_movie_list(subcategory)
        else:
            show_movies()
    elif category == "shows":
        show_tv_shows()
    elif category == "settings":
        xbmcaddon.Addon().openSettings()
