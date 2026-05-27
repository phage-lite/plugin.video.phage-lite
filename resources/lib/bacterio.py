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

    if action == "select_source":
        from services.player import resolve_and_play
        resolve_and_play(
            item_type=params.get("type", "movie"),
            tmdb_id=params.get("id", ""),
            handle=HANDLE,
            season=params.get("season", ""),
            episode=params.get("episode", ""),
            force_select=True,
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

    if action == "trakt_watchlist_add":
        from services.trakt import Trakt
        from utils.notifications import info
        tmdb_id_str = params.get("id", "")
        item_type = params.get("type", "movie")
        if tmdb_id_str:
            if Trakt.is_authenticated:
                Trakt.add_to_watchlist(item_type, int(tmdb_id_str))
                info("Added to Trakt Watchlist")
            else:
                error("Connect Trakt in Settings to use watchlist")
        return

    if action == "trakt_watchlist_remove":
        from services.trakt import Trakt
        from utils.notifications import info
        tmdb_id_str = params.get("id", "")
        item_type = params.get("type", "movie")
        if tmdb_id_str and Trakt.is_authenticated:
            Trakt.remove_from_watchlist(item_type, int(tmdb_id_str))
            info("Removed from Trakt Watchlist")
        return

    if action == "trakt_mark_watched":
        from services.trakt import Trakt
        from utils.notifications import info
        tmdb_id_str = params.get("id", "")
        item_type = params.get("type", "movie")
        season_str = params.get("season", "")
        episode_str = params.get("episode", "")
        if not tmdb_id_str:
            return
        if not Trakt.is_authenticated:
            error("Connect Trakt in Settings to mark as watched")
            return
        if item_type == "movie":
            Trakt.mark_watched_movie(int(tmdb_id_str))
            info("Marked as Watched")
        elif item_type in ("episode", "tv", "show") and season_str and episode_str:
            Trakt.mark_watched_episode(int(tmdb_id_str), int(season_str), int(episode_str))
            info("Marked as Watched")
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
        elif subcategory == "favourites":
            from views.favourites import show_movie_favourites
            show_movie_favourites()
        elif subcategory == "because_you_watched":
            from views.trakt import show_because_you_watched_movies
            _sids = [int(x) for x in unquote_plus(params.get("seed_ids", "")).split(",") if x.strip().isdigit()]
            show_because_you_watched_movies(page, _sids or None, unquote_plus(params.get("seed_title", "")))
        elif subcategory == "because_most_watched":
            from views.trakt import show_because_most_watched_movies
            _sids = [int(x) for x in unquote_plus(params.get("seed_ids", "")).split(",") if x.strip().isdigit()]
            show_because_most_watched_movies(page, _sids or None, unquote_plus(params.get("seed_title", "")))
        elif subcategory == "trakt_watchlist":
            from views.trakt import show_trakt_watchlist_movies
            show_trakt_watchlist_movies(page=page)
        elif subcategory == "trakt_recommendations":
            from views.trakt import show_trakt_recommendations_movies
            show_trakt_recommendations_movies(page=page)
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
        elif subcategory == "favourites":
            from views.favourites import show_show_favourites
            show_show_favourites()
        elif subcategory == "upnext":
            from views.trakt import show_up_next
            show_up_next()
        elif subcategory == "in_progress":
            from views.trakt import show_in_progress_shows
            show_in_progress_shows()
        elif subcategory == "because_you_watched":
            from views.trakt import show_because_you_watched_shows
            _sids = [int(x) for x in unquote_plus(params.get("seed_ids", "")).split(",") if x.strip().isdigit()]
            show_because_you_watched_shows(page, _sids or None, unquote_plus(params.get("seed_title", "")))
        elif subcategory == "because_most_watched":
            from views.trakt import show_because_most_watched_shows
            _sids = [int(x) for x in unquote_plus(params.get("seed_ids", "")).split(",") if x.strip().isdigit()]
            show_because_most_watched_shows(page, _sids or None, unquote_plus(params.get("seed_title", "")))
        elif subcategory == "trakt_watchlist":
            from views.trakt import show_trakt_watchlist_shows
            show_trakt_watchlist_shows(page=page)
        elif subcategory == "trakt_recommendations":
            from views.trakt import show_trakt_recommendations_shows
            show_trakt_recommendations_shows(page=page)
        elif subcategory == "calendar":
            from views.trakt import show_calendar
            show_calendar()
        elif subcategory:
            show_tv_list(subcategory, page=page)
        else:
            show_tv_categories()
        return

    if category == "favourites":
        from views.favourites import show_favourites
        show_favourites()
        return

    if category == "settings":
        xbmcaddon.Addon().openSettings()
        return

    error(f"Unknown route: category={category} action={action}")


if __name__ == "__main__":
    _route()
