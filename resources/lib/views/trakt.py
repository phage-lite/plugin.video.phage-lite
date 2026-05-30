import os
import sys
import xbmcaddon
import xbmcgui
import xbmcplugin
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from services.trakt import Trakt, PAGE_SIZE
from services.tmdb import Tmdb
from utils.notifications import error
from utils.router import url

HANDLE = int(sys.argv[1])
_IMG = "https://image.tmdb.org/t/p/w500"


def _icon(name: str) -> str:
    return os.path.join(xbmcaddon.Addon().getAddonInfo("path"), "resources", "media", "icons", name + ".png")


def _next_page_item(label: str) -> xbmcgui.ListItem:
    li = xbmcgui.ListItem(label=label)
    li.setProperty("SpecialSort", "bottom")
    p = _icon("nextpage")
    li.setArt({"icon": p, "thumb": p, "poster": p})
    return li


# ── Context menu helpers ──────────────────────────────────────────────────────

def _menus_browse(media_type: str, tmdb_id: int, title: str, year: str, poster: str) -> list[tuple[str, str]]:
    """Menus for items NOT in the watchlist - offer to add."""
    fav = url("/favourite/add/", type=media_type, id=tmdb_id, title=title, year=year, poster=poster)
    wl = url("/trakt/watchlist/add/", type=media_type, id=tmdb_id)
    mw = url("/trakt/watched/", type=media_type, id=tmdb_id)
    menus = [
        ("Add to Favourites", f"RunPlugin({fav})"),
        ("Add to Trakt Watchlist", f"RunPlugin({wl})"),
    ]
    if media_type == "movie":
        menus.append(("Mark as Watched", f"RunPlugin({mw})"))
    return menus


def _menus_watchlist(media_type: str, tmdb_id: int, title: str, year: str, poster: str) -> list[tuple[str, str]]:
    """Menus for items already in the Trakt watchlist - offer to remove."""
    fav = url("/favourite/add/", type=media_type, id=tmdb_id, title=title, year=year, poster=poster)
    rem = url("/trakt/watchlist/remove/", type=media_type, id=tmdb_id)
    mw = url("/trakt/watched/", type=media_type, id=tmdb_id)
    menus = [
        ("Add to Favourites", f"RunPlugin({fav})"),
        ("Remove from Trakt Watchlist", f"RunPlugin({rem})"),
    ]
    if media_type == "movie":
        menus.append(("Mark as Watched", f"RunPlugin({mw})"))
    return menus


# ── Up Next ───────────────────────────────────────────────────────────────────

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
            poster, backdrop = _tmdb_images(tmdb_id, "tv")
            return {
                "title":            show.get("title", "Unknown"),
                "tmdb_id":          tmdb_id,
                "season":           int(next_ep.get("season") or 1),
                "episode":          int(next_ep.get("number") or 1),
                "ep_title":         next_ep.get("title") or "",
                "poster":           poster,
                "backdrop":         backdrop,
                "last_watched_at":  watched_item.get("last_watched_at", ""),
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
    title = item["title"]
    season = item["season"]
    episode = item["episode"]
    ep_title = item.get("ep_title") or f"Episode {episode}"
    tmdb_id = item["tmdb_id"]
    poster = item.get("poster", "")
    backdrop = item.get("backdrop", "")

    label = f"{title}  S{season:02d}E{episode:02d}"
    if ep_title and ep_title != f"Episode {episode}":
        label += f" · {ep_title}"

    li = xbmcgui.ListItem(label=label)
    li.setProperty("IsPlayable", "true")
    li.setInfo("video", {
        "title": ep_title,
        "tvshowtitle": title,
        "season": season,
        "episode": episode,
        "mediatype": "episode",
    })
    li.setArt({
        "thumb": f"{_IMG}{backdrop}" if backdrop else f"{_IMG}{poster}" if poster else "",
        "poster": f"{_IMG}{poster}" if poster else "",
        "fanart": f"{_IMG}{backdrop}" if backdrop else "",
    })
    mw = url("/trakt/watched/", type="episode", id=tmdb_id, season=season, episode=episode)
    li.addContextMenuItems([("Mark as Watched", f"RunPlugin({mw})")])
    play_url = url("/play/", type="episode", id=tmdb_id, season=season, episode=episode)
    _ = xbmcplugin.addDirectoryItem(HANDLE, play_url, li, isFolder=False)


# ── Watchlist ─────────────────────────────────────────────────────────────────

def show_trakt_watchlist_movies(page: int = 1):
    try:
        items = Trakt.watchlist_movies(page=page)
    except Exception as e:
        error(f"Trakt error: {e}")
        xbmcplugin.endOfDirectory(HANDLE)
        return

    _warm_images([(int(i.get("movie", {}).get("ids", {}).get("tmdb") or 0), "movie") for i in items])
    xbmcplugin.setContent(HANDLE, "movies")
    for item in items:
        _add_watchlist_movie(item)

    if len(items) >= PAGE_SIZE:
        _ = xbmcplugin.addDirectoryItem(
            HANDLE, url("/movies/trakt_watchlist/", page=page + 1),
            _next_page_item(f"Next Page → ({page + 1})"), isFolder=True
        )
    xbmcplugin.endOfDirectory(HANDLE)


def show_trakt_watchlist_shows(page: int = 1):
    try:
        items = Trakt.watchlist_shows(page=page)
    except Exception as e:
        error(f"Trakt error: {e}")
        xbmcplugin.endOfDirectory(HANDLE)
        return

    _warm_images([(int(i.get("show", {}).get("ids", {}).get("tmdb") or 0), "tv") for i in items])
    xbmcplugin.setContent(HANDLE, "tvshows")
    for item in items:
        _add_watchlist_show(item)

    if len(items) >= PAGE_SIZE:
        _ = xbmcplugin.addDirectoryItem(
            HANDLE, url("/shows/trakt_watchlist/", page=page + 1),
            _next_page_item(f"Next Page → ({page + 1})"), isFolder=True
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

    _warm_images([(int(i.get("ids", {}).get("tmdb") or 0), "movie") for i in items])
    xbmcplugin.setContent(HANDLE, "movies")
    for item in items:
        _add_recommendation_movie(item)

    if len(items) >= PAGE_SIZE:
        _ = xbmcplugin.addDirectoryItem(
            HANDLE, url("/movies/trakt_recommendations/", page=page + 1),
            _next_page_item(f"Next Page → ({page + 1})"), isFolder=True
        )
    xbmcplugin.endOfDirectory(HANDLE)


def show_trakt_recommendations_shows(page: int = 1):
    try:
        items = Trakt.recommendations_shows(page=page)
    except Exception as e:
        error(f"Trakt error: {e}")
        xbmcplugin.endOfDirectory(HANDLE)
        return

    _warm_images([(int(i.get("ids", {}).get("tmdb") or 0), "tv") for i in items])
    xbmcplugin.setContent(HANDLE, "tvshows")
    for item in items:
        _add_recommendation_show(item)

    if len(items) >= PAGE_SIZE:
        _ = xbmcplugin.addDirectoryItem(
            HANDLE, url("/shows/trakt_recommendations/", page=page + 1),
            _next_page_item(f"Next Page → ({page + 1})"), isFolder=True
        )
    xbmcplugin.endOfDirectory(HANDLE)


# ── Item renderers ────────────────────────────────────────────────────────────

def _tmdb_images(tmdb_id: int, media: str) -> tuple[str, str]:
    try:
        d = Tmdb.movie_details(tmdb_id) if media == "movie" else Tmdb.tv_details(tmdb_id)
        return d.get("poster_path") or "", d.get("backdrop_path") or ""
    except Exception:
        return "", ""


def _warm_images(pairs: list[tuple[int, str]]) -> None:
    """Pre-fetch TMDB details for all items in parallel to warm the disk cache."""
    def fetch(pair: tuple[int, str]) -> None:
        tid, media = pair
        if tid:
            _tmdb_images(tid, media)
    with ThreadPoolExecutor(max_workers=8) as ex:
        list(ex.map(fetch, pairs))


def _add_watchlist_movie(item: dict[str, Any]):
    movie = item.get("movie", {})
    tmdb_id: int = int(movie.get("ids", {}).get("tmdb") or 0)
    title = movie.get("title", "Unknown")
    year = int(movie.get("year") or 0)
    overview = movie.get("overview", "")
    year_str = str(year) if year else ""

    poster, backdrop = _tmdb_images(tmdb_id, "movie") if tmdb_id else ("", "")

    li = xbmcgui.ListItem(label=f"{title} ({year})" if year else title)
    li.setProperty("IsPlayable", "true")
    li.setInfo("video", {"title": title, "plot": overview, "year": year, "mediatype": "movie"})
    li.setArt({
        "thumb": f"{_IMG}{poster}" if poster else "",
        "poster": f"{_IMG}{poster}" if poster else "",
        "fanart": f"{_IMG}{backdrop}" if backdrop else "",
    })
    if tmdb_id:
        li.addContextMenuItems(_menus_watchlist("movie", tmdb_id, title, year_str, poster))
        _ = xbmcplugin.addDirectoryItem(HANDLE, url("/play/", type="movie", id=tmdb_id), li, isFolder=False)


def _add_watchlist_show(item: dict[str, Any]):
    show = item.get("show", {})
    tmdb_id: int = int(show.get("ids", {}).get("tmdb") or 0)
    title = show.get("title", "Unknown")
    year = int(show.get("year") or 0)
    overview = show.get("overview", "")
    year_str = str(year) if year else ""

    poster, backdrop = _tmdb_images(tmdb_id, "tv") if tmdb_id else ("", "")

    li = xbmcgui.ListItem(label=f"{title} ({year})" if year else title)
    li.setInfo("video", {"title": title, "plot": overview, "year": year, "mediatype": "tvshow"})
    li.setArt({
        "thumb": f"{_IMG}{poster}" if poster else "",
        "poster": f"{_IMG}{poster}" if poster else "",
        "fanart": f"{_IMG}{backdrop}" if backdrop else "",
    })
    if tmdb_id:
        li.addContextMenuItems(_menus_watchlist("show", tmdb_id, title, year_str, poster))
        show_url = url("/show/:show_id/seasons/", show_id=tmdb_id, show_title=title)
        _ = xbmcplugin.addDirectoryItem(HANDLE, show_url, li, isFolder=True)


def _add_recommendation_movie(item: dict[str, Any]):
    tmdb_id: int = int(item.get("ids", {}).get("tmdb") or 0)
    title = item.get("title", "Unknown")
    year = int(item.get("year") or 0)
    overview = item.get("overview", "")
    year_str = str(year) if year else ""

    poster, backdrop = _tmdb_images(tmdb_id, "movie") if tmdb_id else ("", "")

    li = xbmcgui.ListItem(label=f"{title} ({year})" if year else title)
    li.setProperty("IsPlayable", "true")
    li.setInfo("video", {"title": title, "plot": overview, "year": year, "mediatype": "movie"})
    li.setArt({
        "thumb": f"{_IMG}{poster}" if poster else "",
        "poster": f"{_IMG}{poster}" if poster else "",
        "fanart": f"{_IMG}{backdrop}" if backdrop else "",
    })
    if tmdb_id:
        li.addContextMenuItems(_menus_browse("movie", tmdb_id, title, year_str, poster))
        _ = xbmcplugin.addDirectoryItem(HANDLE, url("/play/", type="movie", id=tmdb_id), li, isFolder=False)


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
    _warm_images([(int(i.get("show", {}).get("ids", {}).get("tmdb") or 0), "tv") for i in all_items])
    xbmcplugin.setContent(HANDLE, "episodes")
    for date_str in sorted(data.keys()):
        for ep_item in data[date_str]:
            _add_calendar_item(date_str, ep_item)
    xbmcplugin.endOfDirectory(HANDLE)


def _add_calendar_item(date_str: str, item: dict[str, Any]):
    show = item.get("show", {})
    ep = item.get("episode", {})
    tmdb_id: int = int(show.get("ids", {}).get("tmdb") or 0)
    show_title = show.get("title", "Unknown")
    season = int(ep.get("season") or 1)
    episode = int(ep.get("number") or 1)
    ep_title = ep.get("title") or f"Episode {episode}"
    overview = ep.get("overview", "")
    rating = float(ep.get("rating") or 0)

    poster, backdrop = _tmdb_images(tmdb_id, "tv") if tmdb_id else ("", "")

    label = f"[{date_str}]  {show_title}  S{season:02d}E{episode:02d} · {ep_title}"
    li = xbmcgui.ListItem(label=label)
    li.setProperty("IsPlayable", "true")
    li.setInfo("video", {
        "title": ep_title,
        "tvshowtitle": show_title,
        "season": season,
        "episode": episode,
        "plot": overview,
        "rating": rating,
        "aired": date_str,
        "mediatype": "episode",
    })
    li.setArt({
        "thumb": f"{_IMG}{backdrop}" if backdrop else f"{_IMG}{poster}" if poster else "",
        "poster": f"{_IMG}{poster}" if poster else "",
        "fanart": f"{_IMG}{backdrop}" if backdrop else "",
    })
    if tmdb_id:
        mw = url("/trakt/watched/", type="episode", id=tmdb_id, season=season, episode=episode)
        li.addContextMenuItems([("Mark as Watched", f"RunPlugin({mw})")])
        play_url = url("/play/", type="episode", id=tmdb_id, season=season, episode=episode)
        _ = xbmcplugin.addDirectoryItem(HANDLE, play_url, li, isFolder=False)


# ── Item renderers ────────────────────────────────────────────────────────────

def _add_recommendation_show(item: dict[str, Any]):
    tmdb_id: int = int(item.get("ids", {}).get("tmdb") or 0)
    title = item.get("title", "Unknown")
    year = int(item.get("year") or 0)
    overview = item.get("overview", "")
    year_str = str(year) if year else ""

    poster, backdrop = _tmdb_images(tmdb_id, "tv") if tmdb_id else ("", "")

    li = xbmcgui.ListItem(label=f"{title} ({year})" if year else title)
    li.setInfo("video", {"title": title, "plot": overview, "year": year, "mediatype": "tvshow"})
    li.setArt({
        "thumb": f"{_IMG}{poster}" if poster else "",
        "poster": f"{_IMG}{poster}" if poster else "",
        "fanart": f"{_IMG}{backdrop}" if backdrop else "",
    })
    if tmdb_id:
        li.addContextMenuItems(_menus_browse("show", tmdb_id, title, year_str, poster))
        show_url = url("/show/:show_id/seasons/", show_id=tmdb_id, show_title=title)
        _ = xbmcplugin.addDirectoryItem(HANDLE, show_url, li, isFolder=True)


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
        _ = xbmcgui.Dialog().ok("In Progress", "No shows in progress.\n\nStart watching a show to see it here.")
        xbmcplugin.endOfDirectory(HANDLE)
        return

    results.sort(key=lambda x: x.get("last_watched_at", ""), reverse=True)
    _warm_images([(r["tmdb_id"], "tv") for r in results])
    xbmcplugin.setContent(HANDLE, "tvshows")

    for r in results:
        tmdb_id = r["tmdb_id"]
        title = r["title"]
        year = r["year"]
        poster, backdrop = _tmdb_images(tmdb_id, "tv")
        label = f"{title} ({year})" if year else title
        li = xbmcgui.ListItem(label=label)
        li.setInfo("video", {"title": title, "year": year, "mediatype": "tvshow"})
        li.setArt({
            "thumb": f"{_IMG}{poster}" if poster else "",
            "poster": f"{_IMG}{poster}" if poster else "",
            "fanart": f"{_IMG}{backdrop}" if backdrop else "",
        })
        show_url = url("/show/:show_id/seasons/", show_id=tmdb_id, show_title=title)
        _ = xbmcplugin.addDirectoryItem(HANDLE, show_url, li, isFolder=True)

    xbmcplugin.endOfDirectory(HANDLE)


# ── Because You/Most Watched ──────────────────────────────────────────────────

def _render_tmdb_shows(items: list[dict[str, Any]], next_url: str = "") -> None:
    xbmcplugin.setContent(HANDLE, "tvshows")
    for show in items:
        title = show.get("name", "Unknown")
        overview = show.get("overview", "")
        poster = show.get("poster_path") or ""
        backdrop = show.get("backdrop_path") or ""
        rating = float(show.get("vote_average") or 0)
        year_str = (show.get("first_air_date") or "")[:4]
        tmdb_id = int(show.get("id") or 0)
        li = xbmcgui.ListItem(label=title)
        li.setInfo("video", {
            "title": title, "plot": overview,
            "year": int(year_str) if year_str.isdigit() else 0,
            "rating": rating, "mediatype": "tvshow",
        })
        li.setArt({
            "thumb": f"{_IMG}{poster}" if poster else "",
            "poster": f"{_IMG}{poster}" if poster else "",
            "fanart": f"{_IMG}{backdrop}" if backdrop else "",
        })
        li.addContextMenuItems(_menus_browse("show", tmdb_id, title, year_str, poster))
        show_url = url("/show/:show_id/seasons/", show_id=tmdb_id, show_title=title)
        _ = xbmcplugin.addDirectoryItem(HANDLE, show_url, li, isFolder=True)
    if next_url:
        li = xbmcgui.ListItem(label="Next Page →")
        _ = xbmcplugin.addDirectoryItem(HANDLE, next_url, li, isFolder=True)
    xbmcplugin.endOfDirectory(HANDLE)


def _render_tmdb_movies(items: list[dict[str, Any]], next_url: str = "") -> None:
    xbmcplugin.setContent(HANDLE, "movies")
    for movie in items:
        title = movie.get("title", "Unknown")
        overview = movie.get("overview", "")
        poster = movie.get("poster_path") or ""
        backdrop = movie.get("backdrop_path") or ""
        rating = float(movie.get("vote_average") or 0)
        year_str = (movie.get("release_date") or "")[:4]
        tmdb_id = int(movie.get("id") or 0)
        li = xbmcgui.ListItem(label=title)
        li.setProperty("IsPlayable", "true")
        li.setInfo("video", {
            "title": title, "plot": overview,
            "year": int(year_str) if year_str.isdigit() else 0,
            "rating": rating, "mediatype": "movie",
        })
        li.setArt({
            "thumb": f"{_IMG}{poster}" if poster else "",
            "poster": f"{_IMG}{poster}" if poster else "",
            "fanart": f"{_IMG}{backdrop}" if backdrop else "",
        })
        li.addContextMenuItems(_menus_browse("movie", tmdb_id, title, year_str, poster))
        _ = xbmcplugin.addDirectoryItem(HANDLE, url("/play/", type="movie", id=tmdb_id), li, isFolder=False)
    if next_url:
        li = xbmcgui.ListItem(label="Next Page →")
        _ = xbmcplugin.addDirectoryItem(HANDLE, next_url, li, isFolder=True)
    xbmcplugin.endOfDirectory(HANDLE)


_N_SEEDS = 3  # number of watch-history seeds to aggregate


def _because_shows(page: int, seed_ids: list[int], seed_title: str, sort_key: str, subcategory: str) -> None:
    if not seed_ids:
        try:
            watched = Trakt.watched_shows(limit=50)
            if not watched:
                _ = xbmcgui.Dialog().ok("Nothing found", "No watch history found on Trakt.")
                xbmcplugin.endOfDirectory(HANDLE)
                return
            if sort_key == "plays":
                watched.sort(key=lambda x: int(x.get("plays") or 0), reverse=True)
            else:
                watched.sort(key=lambda x: x.get("last_watched_at", "") or "", reverse=True)
            seeds = watched[:_N_SEEDS]
            seed_ids = [int(s.get("show", {}).get("ids", {}).get("tmdb") or 0) for s in seeds]
            seed_ids = [sid for sid in seed_ids if sid]
            seed_title = seeds[0].get("show", {}).get("title", "") if seeds else ""
        except Exception as e:
            error(f"Trakt error: {e}")
            xbmcplugin.endOfDirectory(HANDLE)
            return

    if not seed_ids:
        _ = xbmcgui.Dialog().ok("Nothing found", "Could not determine seeds from your history.")
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
        url(f"/shows/{subcategory}/", seed_ids=seed_param, seed_title=seed_title, page=page + 1)
        if len(merged) >= 20 else ""
    )
    _render_tmdb_shows(merged, next_url)


def show_because_you_watched_shows(page: int = 1, seed_ids: list[int] | None = None, seed_title: str = "") -> None:
    _because_shows(page, seed_ids or [], seed_title, "last_watched_at", "because_you_watched")


def show_because_most_watched_shows(page: int = 1, seed_ids: list[int] | None = None, seed_title: str = "") -> None:
    _because_shows(page, seed_ids or [], seed_title, "plays", "because_most_watched")


def _because_movies(page: int, seed_ids: list[int], seed_title: str, sort_key: str, subcategory: str) -> None:
    if not seed_ids:
        try:
            watched = Trakt.watched_movies(limit=50)
            if not watched:
                _ = xbmcgui.Dialog().ok("Nothing found", "No watch history found on Trakt.")
                xbmcplugin.endOfDirectory(HANDLE)
                return
            if sort_key == "plays":
                watched.sort(key=lambda x: int(x.get("plays") or 0), reverse=True)
            else:
                watched.sort(key=lambda x: x.get("last_watched_at", "") or "", reverse=True)
            seeds = watched[:_N_SEEDS]
            seed_ids = [int(s.get("movie", {}).get("ids", {}).get("tmdb") or 0) for s in seeds]
            seed_ids = [sid for sid in seed_ids if sid]
            seed_title = seeds[0].get("movie", {}).get("title", "") if seeds else ""
        except Exception as e:
            error(f"Trakt error: {e}")
            xbmcplugin.endOfDirectory(HANDLE)
            return

    if not seed_ids:
        _ = xbmcgui.Dialog().ok("Nothing found", "Could not determine seeds from your history.")
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
        url(f"/movies/{subcategory}/", seed_ids=seed_param, seed_title=seed_title, page=page + 1)
        if len(merged) >= 20 else ""
    )
    _render_tmdb_movies(merged, next_url)


def show_because_you_watched_movies(page: int = 1, seed_ids: list[int] | None = None, seed_title: str = "") -> None:
    _because_movies(page, seed_ids or [], seed_title, "last_watched_at", "because_you_watched")


def show_because_most_watched_movies(page: int = 1, seed_ids: list[int] | None = None, seed_title: str = "") -> None:
    _because_movies(page, seed_ids or [], seed_title, "plays", "because_most_watched")
