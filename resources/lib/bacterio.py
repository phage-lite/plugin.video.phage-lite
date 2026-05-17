import sys
import xbmcaddon
from urllib.parse import parse_qsl, unquote_plus

from utils.notifications import error

HANDLE = int(sys.argv[1])


def _params() -> dict[str, str]:
    return dict(parse_qsl(sys.argv[2].lstrip("?")))


def _route():
    params = _params()
    action = params.get("action")
    category = params.get("category")
    subcategory = params.get("subcategory")
    genre_id = params.get("genre_id")
    genre_name = unquote_plus(params.get("genre_name", ""))
    page = int(params.get("page", "1"))

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

    if action == "search":
        from views.search import do_search
        do_search(query=unquote_plus(params.get("query", "")), page=page)
        return

    if action == "favourite_add":
        from views.favourites import add_favourite
        add_favourite(
            item_type=params.get("type", "movie"),
            tmdb_id=params.get("id", ""),
            title=unquote_plus(params.get("title", "")),
            year=params.get("year", ""),
            poster=unquote_plus(params.get("poster", "")),
        )
        return

    if action == "favourite_remove":
        from views.favourites import remove_favourite
        remove_favourite(key=unquote_plus(params.get("key", "")))
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
            show_movies_by_genre(int(genre_id), genre_name, page=page)
        elif subcategory:
            show_movie_list(subcategory, page=page)
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
            show_shows_by_genre(int(genre_id), genre_name, page=page)
        elif subcategory:
            show_tv_list(subcategory, page=page)
        else:
            show_tv_categories()
        return

    if category == "favourites":
        from views.favourites import show_favourites
        show_favourites()
        return

    if category == "trakt":
        from views.trakt import (
            show_trakt_categories,
            show_trakt_watchlist_movies,
            show_trakt_watchlist_shows,
            show_trakt_recommendations_movies,
            show_trakt_recommendations_shows,
        )
        match subcategory:
            case "watchlist" | "recommendations":
                show_trakt_categories(subcategory)
            case "watchlist_movies":
                show_trakt_watchlist_movies(page=page)
            case "watchlist_shows":
                show_trakt_watchlist_shows(page=page)
            case "recommendations_movies":
                show_trakt_recommendations_movies(page=page)
            case "recommendations_shows":
                show_trakt_recommendations_shows(page=page)
            case _:
                error(f"Unknown trakt subcategory: {subcategory}")
        return

    if category == "settings":
        xbmcaddon.Addon().openSettings()
        return

    error(f"Unknown route: category={category} action={action}")


if __name__ == "__main__":
    _route()
