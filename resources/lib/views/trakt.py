import os
import sys
import xbmcaddon
import xbmcgui
import xbmcplugin
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from items import EpisodeItem, MovieItem, ShowItem
from services.trakt import Trakt, PAGE_SIZE
from services.tmdb import Tmdb
from utils.notifications import error
from utils.router import url

HANDLE = int(sys.argv[1])


def _icon(name: str) -> str:
    return os.path.join(
        xbmcaddon.Addon().getAddonInfo("path"),
        "resources",
        "media",
        "icons",
        name + ".png",
    )


def _next_page_item(label: str) -> xbmcgui.ListItem:
    li = xbmcgui.ListItem(label=label)
    li.setProperty("SpecialSort", "bottom")
    p = _icon("nextpage")
    li.setArt({"icon": p, "thumb": p, "poster": p})
    return li


def show_up_next():
    try:
        items = _fetch_up_next()
    except Exception as e:
        error(f"Up Next error: {e}")
        xbmcplugin.endOfDirectory(HANDLE)
        return

    if not items:
        _ = xbmcgui.Dialog().ok(
            "Up Next",
            "Nothing up next.\n\nAdd shows to your Trakt Watchlist and watch some episodes to get started.",
        )
        xbmcplugin.endOfDirectory(HANDLE)
        return

    xbmcplugin.setContent(HANDLE, "episodes")
    for item in items:
        _add_up_next_item(item)
    xbmcplugin.endOfDirectory(HANDLE)


def _fetch_up_next() -> list[dict[str, Any]]:
    watched = Trakt.watched_shows(limit=30)

    def _progress(watched_item: dict[str, Any]) -> dict[str, Any] | None:
        show = watched_item.get("show", {})
        trakt_id: int | None = show.get("ids", {}).get("trakt")
        tmdb_id: int | None = show.get("ids", {}).get("tmdb")
        if not trakt_id or not tmdb_id:
            return None
        try:
            prog = Trakt.show_progress(trakt_id)
            next_ep = prog.get("next_episode")
            if not next_ep:
                return None
            show_details = Tmdb.tv_show_details(tmdb_id)
            season_number = next_ep.get("season", 1)
            episode_number = next_ep.get("number", 1)
            season_details = Tmdb.tv_season(tmdb_id, season_number)
            return {
                "episode_number": episode_number,
                "show_details": show_details,
                "season_details": season_details,
                "last_watched_at": watched_item.get("last_watched_at", ""),
            }
        except Exception:
            return None

    results: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(_progress, item) for item in watched]
        for future in as_completed(futures):
            val = future.result()
            if val:
                results.append(val)

    results.sort(key=lambda x: x.get("last_watched_at", ""), reverse=True)
    return results


def _add_up_next_item(item: dict[str, Any]):
    episode_number = item["episode_number"]
    show_details = item["show_details"]
    season_details = item["season_details"]

    # label = f"{show_title}: S{season:02d}E{episode_num:02d}"
    # if ep_title and ep_title != f"Episode {episode_num}":
    #     label += f" - {ep_title}"
    episode_item = EpisodeItem(episode_number, season_details, show_details)
    label = (
        f"{episode_item.show_title}: S{episode_item.season_number}E{episode_item.label}"
    )
    episode_item.listItem.setLabel(label)
    episode_item.listItem.setLabel2(label)

    _ = xbmcplugin.addDirectoryItem(HANDLE, episode_item.url, episode_item.listItem)


# ── Watchlist ─────────────────────────────────────────────────────────────────


def show_trakt_watchlist_movies(page: int = 1):
    try:
        items = Trakt.watchlist_movies(page=page)
    except Exception as e:
        error(f"Trakt error: {e}")
        xbmcplugin.endOfDirectory(HANDLE)
        return

    _warm_details(
        [
            (int(i.get("movie", {}).get("ids", {}).get("tmdb") or 0), "movie")
            for i in items
        ]
    )
    xbmcplugin.setContent(HANDLE, "movies")
    for item in items:
        _add_watchlist_movie(item)

    if len(items) >= PAGE_SIZE:
        _ = xbmcplugin.addDirectoryItem(
            HANDLE,
            url("/movies/trakt_watchlist/", page=page + 1),
            _next_page_item(f"Next Page → ({page + 1})"),
            isFolder=True,
        )
    xbmcplugin.endOfDirectory(HANDLE)


def show_trakt_watchlist_shows(page: int = 1):
    try:
        items = Trakt.watchlist_shows(page=page)
    except Exception as e:
        error(f"Trakt error: {e}")
        xbmcplugin.endOfDirectory(HANDLE)
        return

    _warm_details(
        [(int(i.get("show", {}).get("ids", {}).get("tmdb") or 0), "tv") for i in items]
    )
    xbmcplugin.setContent(HANDLE, "tvshows")
    for item in items:
        _add_watchlist_show(item)

    if len(items) >= PAGE_SIZE:
        _ = xbmcplugin.addDirectoryItem(
            HANDLE,
            url("/shows/trakt_watchlist/", page=page + 1),
            _next_page_item(f"Next Page → ({page + 1})"),
            isFolder=True,
        )
    xbmcplugin.endOfDirectory(HANDLE)


# ── Recommendations ───────────────────────────────────────────────────────────


def show_trakt_recommendations_movies(page: int = 1):
    try:
        items = Trakt.recommendations_movies(page=page)
    except Exception as e:
        error(f"Trakt error: {e}")
        xbmcplugin.endOfDirectory(HANDLE)
        return

    _warm_details([(int(i.get("ids", {}).get("tmdb") or 0), "movie") for i in items])
    xbmcplugin.setContent(HANDLE, "movies")
    for item in items:
        _add_recommendation_movie(item)

    if len(items) >= PAGE_SIZE:
        _ = xbmcplugin.addDirectoryItem(
            HANDLE,
            url("/movies/trakt_recommendations/", page=page + 1),
            _next_page_item(f"Next Page → ({page + 1})"),
            isFolder=True,
        )
    xbmcplugin.endOfDirectory(HANDLE)


def show_trakt_recommendations_shows(page: int = 1):
    try:
        items = Trakt.recommendations_shows(page=page)
    except Exception as e:
        error(f"Trakt error: {e}")
        xbmcplugin.endOfDirectory(HANDLE)
        return

    _warm_details([(int(i.get("ids", {}).get("tmdb") or 0), "tv") for i in items])
    xbmcplugin.setContent(HANDLE, "tvshows")
    for item in items:
        _add_recommendation_show(item)

    if len(items) >= PAGE_SIZE:
        _ = xbmcplugin.addDirectoryItem(
            HANDLE,
            url("/shows/trakt_recommendations/", page=page + 1),
            _next_page_item(f"Next Page → ({page + 1})"),
            isFolder=True,
        )
    xbmcplugin.endOfDirectory(HANDLE)


# ── Item renderers ────────────────────────────────────────────────────────────


def _warm_details(pairs: list[tuple[int, str]]) -> None:
    """Pre-fetch TMDB details for all items in parallel to warm the disk cache."""

    def fetch(pair: tuple[int, str]) -> None:
        tid, media = pair
        if not tid:
            return
        try:
            if media == "movie":
                _ = Tmdb.movie_rich_details(tid)
            else:
                _ = Tmdb.tv_show_details(tid)
        except Exception:
            pass

    with ThreadPoolExecutor(max_workers=8) as ex:
        _ = list(ex.map(fetch, pairs))


def _add_watchlist_movie(item: dict[str, Any]):
    movie = item.get("movie", {})
    tmdb_id: int = int(movie.get("ids", {}).get("tmdb") or 0)
    if not tmdb_id:
        return
    try:
        details = Tmdb.movie_rich_details(tmdb_id)
    except Exception:
        return
    movie_item = MovieItem(details)
    _ = xbmcplugin.addDirectoryItem(
        HANDLE, movie_item.url, movie_item.listItem, isFolder=False
    )


def _add_watchlist_show(item: dict[str, Any]):
    show = item.get("show", {})
    tmdb_id: int = int(show.get("ids", {}).get("tmdb") or 0)
    if not tmdb_id:
        return
    try:
        details = Tmdb.tv_show_details(tmdb_id)
    except Exception:
        return
    show_item = ShowItem(details)
    _ = xbmcplugin.addDirectoryItem(
        HANDLE, show_item.url, show_item.listItem, isFolder=True
    )


def _add_recommendation_movie(item: dict[str, Any]):
    tmdb_id: int = int(item.get("ids", {}).get("tmdb") or 0)
    if not tmdb_id:
        return
    try:
        details = Tmdb.movie_rich_details(tmdb_id)
    except Exception:
        return
    movie_item = MovieItem(details)
    _ = xbmcplugin.addDirectoryItem(
        HANDLE, movie_item.url, movie_item.listItem, isFolder=False
    )


# ── Calendar ──────────────────────────────────────────────────────────────────


def show_calendar():
    try:
        data = Trakt.my_calendar(days=7)
    except Exception as e:
        error(f"Trakt error: {e}")
        xbmcplugin.endOfDirectory(HANDLE)
        return

    if not data:
        _ = xbmcgui.Dialog().ok(
            "My Calendar",
            "No upcoming episodes in the next 7 days.\n\nMake sure shows are in your Trakt Watchlist.",
        )
        xbmcplugin.endOfDirectory(HANDLE)
        return

    all_items = [ep_item for eps in data.values() for ep_item in eps]
    _warm_details(
        [
            (int(i.get("show", {}).get("ids", {}).get("tmdb") or 0), "tv")
            for i in all_items
        ]
    )
    xbmcplugin.setContent(HANDLE, "episodes")
    for date_str in sorted(data.keys()):
        for ep_item in data[date_str]:
            _add_calendar_item(date_str, ep_item)
    xbmcplugin.endOfDirectory(HANDLE)


def _add_calendar_item(date_str: str, item: dict[str, Any]):
    show = item.get("show", {})
    ep_data = item.get("episode", {})
    tmdb_id: int = int(show.get("ids", {}).get("tmdb") or 0)
    if not tmdb_id:
        return
    show_title = show.get("title", "Unknown")
    season = int(ep_data.get("season") or 1)
    episode = int(ep_data.get("number") or 1)
    ep_title = ep_data.get("title") or f"Episode {episode}"

    try:
        show_details = Tmdb.tv_show_details(tmdb_id)
        season_data = Tmdb.tv_season(tmdb_id, season)
    except Exception:
        return

    label = f"[{date_str}]  {show_title}  S{season:02d}E{episode:02d} · {ep_title}"
    episode_item = EpisodeItem(episode, season_data, show_details)
    episode_item.listItem.setLabel(label)
    _ = xbmcplugin.addDirectoryItem(
        HANDLE, episode_item.url, episode_item.listItem, isFolder=False
    )


# ── Item renderers ────────────────────────────────────────────────────────────


def _add_recommendation_show(item: dict[str, Any]):
    tmdb_id: int = int(item.get("ids", {}).get("tmdb") or 0)
    if not tmdb_id:
        return
    try:
        details = Tmdb.tv_show_details(tmdb_id)
    except Exception:
        return
    show_item = ShowItem(details)
    _ = xbmcplugin.addDirectoryItem(
        HANDLE, show_item.url, show_item.listItem, isFolder=True
    )


# ── In Progress Shows ─────────────────────────────────────────────────────────


def show_in_progress_shows():
    try:
        watched = Trakt.watched_shows(limit=50)
    except Exception as e:
        error(f"Trakt error: {e}")
        xbmcplugin.endOfDirectory(HANDLE)
        return

    def _check(item: dict[str, Any]) -> dict[str, Any] | None:
        show = item.get("show", {})
        trakt_id: int | None = show.get("ids", {}).get("trakt")
        tmdb_id: int | None = show.get("ids", {}).get("tmdb")
        if not trakt_id or not tmdb_id:
            return None
        try:
            prog = Trakt.show_progress(trakt_id)
            if not prog.get("next_episode"):
                return None
            return {
                "tmdb_id": tmdb_id,
                "title": show.get("title", "Unknown"),
                "year": int(show.get("year") or 0),
                "last_watched_at": item.get("last_watched_at", ""),
            }
        except Exception:
            return None

    results: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=5) as ex:
        futures = [ex.submit(_check, item) for item in watched]
        for future in as_completed(futures):
            val = future.result()
            if val:
                results.append(val)

    if not results:
        _ = xbmcgui.Dialog().ok(
            "In Progress",
            "No shows in progress.\n\nStart watching a show to see it here.",
        )
        xbmcplugin.endOfDirectory(HANDLE)
        return

    results.sort(key=lambda x: x.get("last_watched_at", ""), reverse=True)
    _warm_details([(r["tmdb_id"], "tv") for r in results])
    xbmcplugin.setContent(HANDLE, "tvshows")

    for r in results:
        tmdb_id = r["tmdb_id"]
        try:
            details = Tmdb.tv_show_details(tmdb_id)
        except Exception:
            continue
        show_item = ShowItem(details)
        _ = xbmcplugin.addDirectoryItem(
            HANDLE, show_item.url, show_item.listItem, isFolder=True
        )

    xbmcplugin.endOfDirectory(HANDLE)


# ── Because You/Most Watched ──────────────────────────────────────────────────


def _render_tmdb_shows(items: list[dict[str, Any]], next_url: str = "") -> None:
    xbmcplugin.setContent(HANDLE, "tvshows")
    _warm_details([(int(s.get("id") or 0), "tv") for s in items])
    for show in items:
        tmdb_id = int(show.get("id") or 0)
        try:
            details = Tmdb.tv_show_details(tmdb_id)
        except Exception:
            continue
        show_item = ShowItem(details)
        _ = xbmcplugin.addDirectoryItem(
            HANDLE, show_item.url, show_item.listItem, isFolder=True
        )
    if next_url:
        li = xbmcgui.ListItem(label="Next Page")
        _ = xbmcplugin.addDirectoryItem(HANDLE, next_url, li, isFolder=True)
    xbmcplugin.endOfDirectory(HANDLE)


def _render_tmdb_movies(items: list[dict[str, Any]], next_url: str = "") -> None:
    xbmcplugin.setContent(HANDLE, "movies")
    _warm_details([(int(m.get("id") or 0), "movie") for m in items])
    for movie in items:
        tmdb_id = int(movie.get("id") or 0)
        try:
            details = Tmdb.movie_rich_details(tmdb_id)
        except Exception:
            continue
        movie_item = MovieItem(details)
        _ = xbmcplugin.addDirectoryItem(
            HANDLE, movie_item.url, movie_item.listItem, isFolder=False
        )
    if next_url:
        li = xbmcgui.ListItem(label="Next Page →")
        _ = xbmcplugin.addDirectoryItem(HANDLE, next_url, li, isFolder=True)
    xbmcplugin.endOfDirectory(HANDLE)


_N_SEEDS = 3  # number of watch-history seeds to aggregate


def _because_shows(
    page: int, seed_ids: list[int], seed_title: str, sort_key: str, subcategory: str
) -> None:
    if not seed_ids:
        try:
            watched = Trakt.watched_shows(limit=50)
            if not watched:
                _ = xbmcgui.Dialog().ok(
                    "Nothing found", "No watch history found on Trakt."
                )
                xbmcplugin.endOfDirectory(HANDLE)
                return
            if sort_key == "plays":
                watched.sort(key=lambda x: int(x.get("plays") or 0), reverse=True)
            else:
                watched.sort(
                    key=lambda x: x.get("last_watched_at", "") or "", reverse=True
                )
            seeds = watched[:_N_SEEDS]
            seed_ids = [
                int(s.get("show", {}).get("ids", {}).get("tmdb") or 0) for s in seeds
            ]
            seed_ids = [sid for sid in seed_ids if sid]
            seed_title = seeds[0].get("show", {}).get("title", "") if seeds else ""
        except Exception as e:
            error(f"Trakt error: {e}")
            xbmcplugin.endOfDirectory(HANDLE)
            return

    if not seed_ids:
        _ = xbmcgui.Dialog().ok(
            "Nothing found", "Could not determine seeds from your history."
        )
        xbmcplugin.endOfDirectory(HANDLE)
        return

    xbmcplugin.setPluginCategory(HANDLE, f"Because You Watched: {seed_title}")

    seen: set[int] = set()
    merged: list[dict[str, Any]] = []
    try:
        for sid in seed_ids:
            data = Tmdb.recommended_tv(sid, page)
            for item in data.get("results", []):
                tid = int(item.get("id") or 0)
                if tid and tid not in seen:
                    seen.add(tid)
                    merged.append(item)
    except Exception as e:
        error(f"TMDB error: {e}")
        xbmcplugin.endOfDirectory(HANDLE)
        return

    seed_param = ",".join(str(s) for s in seed_ids)
    next_url = (
        url(
            f"/shows/{subcategory}/",
            seed_ids=seed_param,
            seed_title=seed_title,
            page=page + 1,
        )
        if len(merged) >= 20
        else ""
    )
    _render_tmdb_shows(merged, next_url)


def show_because_you_watched_shows(
    page: int = 1, seed_ids: list[int] | None = None, seed_title: str = ""
) -> None:
    _because_shows(
        page, seed_ids or [], seed_title, "last_watched_at", "because_you_watched"
    )


def show_because_most_watched_shows(
    page: int = 1, seed_ids: list[int] | None = None, seed_title: str = ""
) -> None:
    _because_shows(page, seed_ids or [], seed_title, "plays", "because_most_watched")


def _because_movies(
    page: int, seed_ids: list[int], seed_title: str, sort_key: str, subcategory: str
) -> None:
    if not seed_ids:
        try:
            watched = Trakt.watched_movies(limit=50)
            if not watched:
                _ = xbmcgui.Dialog().ok(
                    "Nothing found", "No watch history found on Trakt."
                )
                xbmcplugin.endOfDirectory(HANDLE)
                return
            if sort_key == "plays":
                watched.sort(key=lambda x: int(x.get("plays") or 0), reverse=True)
            else:
                watched.sort(
                    key=lambda x: x.get("last_watched_at", "") or "", reverse=True
                )
            seeds = watched[:_N_SEEDS]
            seed_ids = [
                int(s.get("movie", {}).get("ids", {}).get("tmdb") or 0) for s in seeds
            ]
            seed_ids = [sid for sid in seed_ids if sid]
            seed_title = seeds[0].get("movie", {}).get("title", "") if seeds else ""
        except Exception as e:
            error(f"Trakt error: {e}")
            xbmcplugin.endOfDirectory(HANDLE)
            return

    if not seed_ids:
        _ = xbmcgui.Dialog().ok(
            "Nothing found", "Could not determine seeds from your history."
        )
        xbmcplugin.endOfDirectory(HANDLE)
        return

    xbmcplugin.setPluginCategory(HANDLE, f"Because You Watched: {seed_title}")

    seen: set[int] = set()
    merged: list[dict[str, Any]] = []
    try:
        for sid in seed_ids:
            data = Tmdb.recommended_movies(sid, page)
            for item in data.get("results", []):
                tid = int(item.get("id") or 0)
                if tid and tid not in seen:
                    seen.add(tid)
                    merged.append(item)
    except Exception as e:
        error(f"TMDB error: {e}")
        xbmcplugin.endOfDirectory(HANDLE)
        return

    seed_param = ",".join(str(s) for s in seed_ids)
    next_url = (
        url(
            f"/movies/{subcategory}/",
            seed_ids=seed_param,
            seed_title=seed_title,
            page=page + 1,
        )
        if len(merged) >= 20
        else ""
    )
    _render_tmdb_movies(merged, next_url)


def show_because_you_watched_movies(
    page: int = 1, seed_ids: list[int] | None = None, seed_title: str = ""
) -> None:
    _because_movies(
        page, seed_ids or [], seed_title, "last_watched_at", "because_you_watched"
    )


def show_because_most_watched_movies(
    page: int = 1, seed_ids: list[int] | None = None, seed_title: str = ""
) -> None:
    _because_movies(page, seed_ids or [], seed_title, "plays", "because_most_watched")
