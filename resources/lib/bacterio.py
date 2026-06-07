import sys
import xbmcaddon

from utils.router import route, dispatch

HANDLE = int(sys.argv[1])


@route("/")
def _home() -> None:
    from views.home import show_home

    show_home()


@route("/search/")
def _search(query: str = "", page: int = 1) -> None:
    from views.search import do_search

    do_search(query=query, page=page)


@route("/favourites/")
def _favourites() -> None:
    from views.favourites import show_favourites

    show_favourites()


@route("/settings/")
def _settings() -> None:
    xbmcaddon.Addon().openSettings()


@route("/play/")
def _play(
    type: str = "movie",
    id: str = "",
    season: str = "",
    episode: str = "",
    scraper: str = "",
) -> None:
    from services.player import resolve_and_play

    resolve_and_play(
        item_type=type,
        tmdb_id=id,
        handle=HANDLE,
        season=season,
        episode=episode,
        scraper_filter=scraper,
    )


@route("/play/select/")
def _play_select(
    type: str = "movie",
    id: str = "",
    season: str = "",
    episode: str = "",
    scraper: str = "",
) -> None:
    from services.player import resolve_and_play

    resolve_and_play(
        item_type=type,
        tmdb_id=id,
        handle=HANDLE,
        season=season,
        episode=episode,
        force_select=True,
        scraper_filter=scraper,
    )


@route("/favourite/add/")
def _favourite_add(
    type: str = "movie", id: str = "", title: str = "", year: str = "", poster: str = ""
) -> None:
    from views.favourites import add_favourite

    add_favourite(item_type=type, tmdb_id=id, title=title, year=year, poster=poster)


@route("/favourite/remove/")
def _favourite_remove(key: str = "") -> None:
    from views.favourites import remove_favourite

    remove_favourite(key=key)


@route("/trakt/watchlist/add/")
def _trakt_wl_add(type: str = "movie", id: str = "") -> None:
    from services.trakt import Trakt
    from utils.notifications import error, info

    if not id:
        return
    if Trakt.is_authenticated:
        Trakt.add_to_watchlist(type, int(id))
        info("Added to Trakt Watchlist")
    else:
        error("Connect Trakt in Settings to use watchlist")


@route("/trakt/watchlist/remove/")
def _trakt_wl_remove(type: str = "movie", id: str = "") -> None:
    from services.trakt import Trakt
    from utils.notifications import info

    if id and Trakt.is_authenticated:
        Trakt.remove_from_watchlist(type, int(id))
        info("Removed from Trakt Watchlist")


@route("/trakt/watched/")
def _trakt_watched(
    type: str = "movie", id: str = "", season: int = 0, episode: int = 0
) -> None:
    from services.trakt import Trakt
    from utils.notifications import error, info

    if not id:
        return
    if not Trakt.is_authenticated:
        error("Connect Trakt in Settings to mark as watched")
        return
    if type == "movie":
        Trakt.mark_watched_movie(int(id))
        info("Marked as Watched")
    elif type in ("episode", "tv", "show") and season and episode:
        Trakt.mark_watched_episode(int(id), season, episode)
        info("Marked as Watched")


@route("/movies/")
def _movies() -> None:
    from views.movies import show_movie_categories

    show_movie_categories()


@route("/movies/genres/")
def _movie_genres() -> None:
    from views.movies import show_movie_genres

    show_movie_genres()


@route("/movies/genre/:genre_id/")
def _movies_by_genre(genre_id: int = 0, genre_name: str = "", page: int = 1) -> None:
    from views.movies import show_movies_by_genre

    show_movies_by_genre(genre_id, genre_name, page=page)


@route("/movies/favourites/")
def _movie_favourites() -> None:
    from views.favourites import show_movie_favourites

    show_movie_favourites()


@route("/movies/because_you_watched/")
def _movies_byw(page: int = 1, seed_ids: list[int] = [], seed_title: str = "") -> None:
    from views.trakt import show_because_you_watched_movies

    show_because_you_watched_movies(page, seed_ids or None, seed_title)


@route("/movies/because_most_watched/")
def _movies_bmw(page: int = 1, seed_ids: list[int] = [], seed_title: str = "") -> None:
    from views.trakt import show_because_most_watched_movies

    show_because_most_watched_movies(page, seed_ids or None, seed_title)


@route("/movies/watchlist/")
def _movies_watchlist(page: int = 1) -> None:
    from views.trakt import show_trakt_watchlist_movies

    show_trakt_watchlist_movies(page=page)


@route("/movies/recommended/")
def _movies_recommended(page: int = 1) -> None:
    from views.trakt import show_trakt_recommendations_movies

    show_trakt_recommendations_movies(page=page)


@route("/movies/:subcategory/")
def _movie_list(subcategory: str = "", page: int = 1) -> None:
    from views.movies import show_movie_list

    show_movie_list(subcategory, page=page)


@route("/shows/")
def _shows() -> None:
    from views.shows import show_tv_categories

    show_tv_categories()


@route("/shows/genres/")
def _show_genres() -> None:
    from views.shows import show_tv_genres

    show_tv_genres()


@route("/shows/genre/:genre_id/")
def _shows_by_genre(genre_id: int = 0, genre_name: str = "", page: int = 1) -> None:
    from views.shows import show_shows_by_genre

    show_shows_by_genre(genre_id, genre_name, page=page)


@route("/shows/favourites/")
def _show_favourites() -> None:
    from views.favourites import show_show_favourites

    show_show_favourites()


@route("/shows/upnext/")
def _show_upnext() -> None:
    from views.trakt import show_up_next

    show_up_next()


@route("/shows/in_progress/")
def _show_in_progress() -> None:
    from views.trakt import show_in_progress_shows

    show_in_progress_shows()


@route("/shows/because_you_watched/")
def _shows_byw(page: int = 1, seed_ids: list[int] = [], seed_title: str = "") -> None:
    from views.trakt import show_because_you_watched_shows

    show_because_you_watched_shows(page, seed_ids or None, seed_title)


@route("/shows/because_most_watched/")
def _shows_bmw(page: int = 1, seed_ids: list[int] = [], seed_title: str = "") -> None:
    from views.trakt import show_because_most_watched_shows

    show_because_most_watched_shows(page, seed_ids or None, seed_title)


@route("/shows/watchlist/")
def _shows_watchlist(page: int = 1) -> None:
    from views.trakt import show_trakt_watchlist_shows

    show_trakt_watchlist_shows(page=page)


@route("/shows/recommended/")
def _shows_recommended(page: int = 1) -> None:
    from views.trakt import show_trakt_recommendations_shows

    show_trakt_recommendations_shows(page=page)


@route("/shows/calendar/")
def _show_calendar() -> None:
    from views.trakt import show_calendar

    show_calendar()


@route("/shows/:subcategory/")
def _show_list(subcategory: str = "", page: int = 1) -> None:
    from views.shows import show_tv_list

    show_tv_list(subcategory, page=page)


@route("/show/:show_id/seasons/")
def _show_seasons(show_id: int = 0, show_title: str = "") -> None:
    from views.shows import show_seasons

    show_seasons(show_id, show_title)


@route("/show/:show_id/season/:season_number/episodes/")
def _show_episodes(show_id: int = 0, season_number: int = 0) -> None:
    from views.shows import show_episodes

    show_episodes(show_id, season_number)


if __name__ == "__main__":
    dispatch()
