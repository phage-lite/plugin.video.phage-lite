import time
import xbmc
import xbmcgui
import xbmcplugin
from threading import Thread

from services.tmdb import Tmdb
from services.real_debrid import RealDebrid
from utils.notifications import error
from utils.logger import log

_SCRAPE_TIMEOUT = 20
_RD_WAIT_TIMEOUT = 60  # seconds to wait for RD to cache a torrent


def resolve_and_play(
    item_type: str,
    tmdb_id: str,
    handle: int,
    season: str = "",
    episode: str = "",
):
    def _fail(msg: str):
        error(msg)
        xbmcplugin.setResolvedUrl(handle, False, xbmcgui.ListItem())

    if not RealDebrid.is_authenticated():
        _fail("RealDebrid not authenticated — go to Settings to connect.")
        return

    # ── 1. Fetch TMDB metadata ───────────────────────────────────────────────
    try:
        if item_type == "episode":
            ext = Tmdb.tv_external_ids(int(tmdb_id))
            details = Tmdb.tv_details(int(tmdb_id))
            title = details.get("name", "")
            year = (details.get("first_air_date") or "")[:4]
            ep_title = _get_episode_title(int(tmdb_id), int(season), int(episode))
        else:
            ext = Tmdb.movie_external_ids(int(tmdb_id))
            details = Tmdb.movie_details(int(tmdb_id))
            title = details.get("title", "")
            year = (details.get("release_date") or "")[:4]
            ep_title = ""
    except Exception as e:
        log(str(e), "resolve_and_play")
        _fail("Could not fetch metadata from TMDB.")
        return

    imdb_id = ext.get("imdb_id") or ""
    if not imdb_id:
        _fail("No IMDB ID found for this title.")
        return

    # ── 2. Build cocoscrapers data dict ──────────────────────────────────────
    if item_type == "episode":
        scrape_data = {
            "tvshowtitle": title,
            "title": ep_title or f"Episode {episode}",
            "year": year,
            "imdb": imdb_id,
            "season": season,
            "episode": episode,
            "aliases": [],
        }
    else:
        scrape_data = {
            "title": title,
            "year": year,
            "imdb": imdb_id,
            "aliases": [],
        }

    # ── 3. Run scrapers with live progress dialog ────────────────────────────
    from services import cocoscrapers as cocos

    if not cocos.is_available():
        _fail("script.module.cocoscrapers is not installed.")
        return

    sources: list = []

    scrape_thread = Thread(target=lambda: sources.extend(cocos.scrape(scrape_data)), daemon=True)
    scrape_thread.start()

    dialog = xbmcgui.DialogProgress()
    dialog.create("Bacterio", f"Searching — {title}…")
    start = time.monotonic()

    while scrape_thread.is_alive():
        elapsed = time.monotonic() - start
        pct = min(int((elapsed / _SCRAPE_TIMEOUT) * 100), 99)
        dialog.update(pct, f"Found {len(sources)} sources…")
        if dialog.iscanceled():
            dialog.close()
            _fail("Cancelled.")
            return
        xbmc.sleep(300)

    dialog.update(100)
    dialog.close()

    if not sources:
        _fail(f"No sources found for {title}.")
        return

    # ── 4. Check RealDebrid instant availability ─────────────────────────────
    hashes = list({
        s.get("hash", "").lower()
        for s in sources
        if len(s.get("hash", "")) == 40
    })

    try:
        cached = RealDebrid.check_instant_availability(hashes)
    except Exception as e:
        log(str(e), "resolve_and_play")
        cached = set()

    # ── 5. Pick best cached source and play ──────────────────────────────────
    magnet = cocos.pick_best_cached(sources, cached)
    if not magnet:
        _fail(f"No RealDebrid-cached sources found for {title}.")
        return

    resolve_magnet_and_play(magnet, handle, title)


def resolve_magnet_and_play(magnet: str, handle: int, title: str = ""):
    def _fail(msg: str):
        error(msg)
        xbmcplugin.setResolvedUrl(handle, False, xbmcgui.ListItem())

    if not RealDebrid.is_authenticated():
        _fail("RealDebrid not authenticated.")
        return

    try:
        torrent = RealDebrid.add_magnet(magnet)
        torrent_id = torrent.get("id")
        if not torrent_id:
            _fail("RealDebrid did not accept the magnet.")
            return

        RealDebrid.select_files(torrent_id)

        dialog = xbmcgui.DialogProgress()
        dialog.create("Bacterio", f"Opening — {title}…" if title else "Opening…")

        iterations = _RD_WAIT_TIMEOUT // 2
        for _ in range(iterations):
            xbmc.sleep(2000)
            info_data = RealDebrid.get_torrent_info(torrent_id)
            status = info_data.get("status", "")
            progress = int(info_data.get("progress") or 0)
            dialog.update(progress, f"RealDebrid: {status}")
            if dialog.iscanceled():
                dialog.close()
                _fail("Cancelled.")
                return
            if status == "downloaded":
                break
        else:
            dialog.close()
            _fail("Timed out waiting for RealDebrid.")
            return

        dialog.close()
        links = info_data.get("links", [])
        if not links:
            _fail("RealDebrid returned no download links.")
            return

        result = RealDebrid.unrestrict_link(links[0])
        direct_url = result.get("download") or result.get("url") or ""
    except Exception as e:
        log(str(e), "resolve_magnet_and_play")
        _fail(f"RealDebrid error: {e}")
        return

    if not direct_url:
        _fail("RealDebrid returned an empty URL.")
        return

    li = xbmcgui.ListItem(path=direct_url)
    xbmcplugin.setResolvedUrl(handle, True, li)


def _get_episode_title(show_id: int, season: int, episode: int) -> str:
    try:
        season_data = Tmdb.tv_season(show_id, season)
        for ep in season_data.get("episodes", []):
            if ep.get("episode_number") == episode:
                return ep.get("name", "")
    except Exception:
        pass
    return ""
