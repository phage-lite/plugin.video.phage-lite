import sys
import xbmcaddon
import xbmcplugin
from urllib.parse import parse_qsl, unquote_plus

from utils.notifications import error

HANDLE = int(sys.argv[1])


def _params() -> dict:
    return dict(parse_qsl(sys.argv[2].lstrip("?")))


def _route():
    params = _params()
    action = params.get("action")
    category = params.get("category")
    subcategory = params.get("subcategory")
    genre_id = params.get("genre_id")
    genre_name = unquote_plus(params.get("genre_name", ""))

    if action == "play":
        from services.player import resolve_and_play
        resolve_and_play(
            item_type=params.get("type", "movie"),
            tmdb_id=params.get("id", ""),
            handle=HANDLE,
            season=params.get("season", ""),
            episode=params.get("episode", ""),
        )
        return

    if action == "seasons":
        show_id = params.get("show_id")
        show_title = unquote_plus(params.get("show_title", ""))
        if show_id:
            from views.shows import show_seasons
            show_seasons(int(show_id), show_title)
        return

    if action == "episodes":
        show_id = params.get("show_id")
        show_title = unquote_plus(params.get("show_title", ""))
        season_number = params.get("season_number")
        if show_id and season_number:
            from views.shows import show_episodes
            show_episodes(int(show_id), show_title, int(season_number))
        return

    if not category:
        from views.home import show_home
        show_home()
        return

    if category == "movies":
        from views.movies import (
            show_movie_categories,
            show_movie_list,
            show_movie_genres,
            show_movies_by_genre,
        )
        if subcategory == "genres":
            show_movie_genres()
        elif subcategory == "genre" and genre_id:
            show_movies_by_genre(int(genre_id), genre_name)
        elif subcategory:
            show_movie_list(subcategory)
        else:
            show_movie_categories()
        return

    if category == "shows":
        from views.shows import (
            show_tv_categories,
            show_tv_list,
            show_tv_genres,
            show_shows_by_genre,
        )
        if subcategory == "genres":
            show_tv_genres()
        elif subcategory == "genre" and genre_id:
            show_shows_by_genre(int(genre_id), genre_name)
        elif subcategory:
            show_tv_list(subcategory)
        else:
            show_tv_categories()
        return

    if category == "settings":
        xbmcaddon.Addon().openSettings()
        return

    error(f"Unknown route: category={category} action={action}")


if __name__ == "__main__":
    _route()
