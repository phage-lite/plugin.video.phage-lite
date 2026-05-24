import time
import xbmc
import xbmcgui
import xbmcplugin
from threading import Thread
from typing import Any

from services.tmdb import Tmdb
from services.real_debrid import RealDebrid
from services.torbox import TorBox
from utils.notifications import error, info
from utils.logger import log
from settings.settings import get_setting

_SCRAPE_TIMEOUT = 20
_POLL_INTERVAL = 2000       # ms
_RD_INITIAL_WAIT = 30       # seconds to wait for waiting_files_selection
_RD_DOWNLOAD_WAIT = 120     # seconds to wait for downloaded
_TB_DOWNLOAD_WAIT = 120     # seconds to wait for TorBox download
_TB_ERROR_STATES = {"error", "failed", "dead"}

_QUALITY_RANK = {"4K": 0, "1080p": 1, "720p": 2, "SD": 3, "CAM": 4, "TELE": 5, "SYNC": 5}
_RD_ERROR_STATUSES = {"magnet_error", "error", "dead", "virus"}


# ── Internal helpers ──────────────────────────────────────────────────────────

def _rd_ok() -> bool:
    return get_setting("rd.enabled") == "true" and RealDebrid.is_authenticated()


def _tb_ok() -> bool:
    return TorBox.is_enabled() and TorBox.is_authenticated()


def _sort_sources(sources: list[dict[str, Any]], cached: set[str]) -> list[dict[str, Any]]:
    quality_pref = get_setting("playback.quality_pref")
    if quality_pref == "1":
        # best quality, ignore cache order
        return sorted(sources, key=lambda s: (
            _QUALITY_RANK.get(s.get("quality", "SD"), 9),
            0 if s.get("hash", "").lower() in cached else 1,
            -int(s.get("seeders") or 0),
        ))
    # default: cached first, then quality
    return sorted(sources, key=lambda s: (
        0 if s.get("hash", "").lower() in cached else 1,
        _QUALITY_RANK.get(s.get("quality", "SD"), 9),
        -int(s.get("seeders") or 0),
    ))


def _add_to_rd(magnet: str, title: str) -> str:
    """
    Add a magnet to RealDebrid and wait for a streamable URL.
    Returns the direct URL on success, or '' on any failure (error status,
    timeout, cancellation). Never calls setResolvedUrl itself.
    """
    progress = xbmcgui.DialogProgress()
    progress.create("Bacterio", f"Opening — {title}…" if title else "Opening…")

    try:
        torrent = RealDebrid.add_magnet(magnet)
        torrent_id = torrent.get("id")
        if not torrent_id:
            return ""

        info_data: dict[str, Any] = {}
        deadline = time.monotonic() + _RD_INITIAL_WAIT
        while time.monotonic() < deadline:
            xbmc.sleep(_POLL_INTERVAL)
            if progress.iscanceled():
                return ""
            info_data = RealDebrid.get_torrent_info(torrent_id)
            status = info_data.get("status", "")
            if status in _RD_ERROR_STATUSES:
                log(f"RD torrent error: {status}", "_add_to_rd")
                return ""
            if status in ("waiting_files_selection", "downloaded"):
                break
        else:
            log("RD timed out waiting for file selection", "_add_to_rd")
            return ""

        if info_data.get("status") != "downloaded":
            RealDebrid.select_files(torrent_id)

        deadline = time.monotonic() + _RD_DOWNLOAD_WAIT
        while time.monotonic() < deadline:
            xbmc.sleep(_POLL_INTERVAL)
            if progress.iscanceled():
                return ""
            info_data = RealDebrid.get_torrent_info(torrent_id)
            status = info_data.get("status", "")
            pct = int(info_data.get("progress") or 0)
            progress.update(pct, f"RealDebrid: {status}")
            if status in _RD_ERROR_STATUSES:
                log(f"RD download error: {status}", "_add_to_rd")
                return ""
            if status == "downloaded":
                break
        else:
            log("RD timed out waiting for download", "_add_to_rd")
            return ""

        links: list[str] = info_data.get("links", [])
        if not links:
            return ""

        result = RealDebrid.unrestrict_link(links[0])
        return result.get("download") or result.get("url") or ""

    except Exception as e:
        log(str(e), "_add_to_rd")
        return ""
    finally:
        progress.close()


def _add_to_torbox(magnet: str, title: str) -> str:
    progress = xbmcgui.DialogProgress()
    progress.create("Bacterio", f"Opening — {title}…" if title else "Opening…")

    try:
        result = TorBox.add_magnet(magnet)
        if not result.get("success"):
            log(f"TorBox add_magnet failed: {result}", "_add_to_torbox")
            return ""

        data = result.get("data") or {}
        torrent_id: int | None = data.get("torrent_id")
        if not torrent_id:
            return ""

        info_data: dict[str, Any] = {}
        deadline = time.monotonic() + _TB_DOWNLOAD_WAIT
        while time.monotonic() < deadline:
            xbmc.sleep(_POLL_INTERVAL)
            if progress.iscanceled():
                return ""
            info_result = TorBox.get_torrent_info(torrent_id)
            raw_data = info_result.get("data") or {}
            info_data: dict[str, Any] = raw_data[0] if isinstance(raw_data, list) and raw_data else raw_data if isinstance(raw_data, dict) else {}
            state: str = info_data.get("download_state", "")
            pct = int(float(info_data.get("progress", 0)) * 100)
            progress.update(pct, f"TorBox: {state}")
            if state in _TB_ERROR_STATES:
                log(f"TorBox error state: {state}", "_add_to_torbox")
                return ""
            if state in ("cached", "completed", "uploading", "seeding"):
                break
        else:
            log("TorBox timed out", "_add_to_torbox")
            return ""

        files: list[dict[str, Any]] = info_data.get("files") or []
        target = TorBox.pick_video_file(files)
        if not target:
            return ""

        file_id: int | None = target.get("id")
        if not file_id:
            return ""

        dl_result = TorBox.request_download(torrent_id, file_id)
        if not dl_result.get("success"):
            return ""
        url = dl_result.get("data", "")
        return url if isinstance(url, str) else ""

    except Exception as e:
        log(str(e), "_add_to_torbox")
        return ""
    finally:
        progress.close()


def _tag_playing(item_type: str, tmdb_id: str, season: str, episode: str) -> None:
    win = xbmcgui.Window(10000)
    win.setProperty("bacterio.type", item_type)
    win.setProperty("bacterio.tmdb_id", tmdb_id)
    win.setProperty("bacterio.season", season)
    win.setProperty("bacterio.episode", episode)


def _play_url(direct_url: str, handle: int):
    li = xbmcgui.ListItem(path=direct_url)
    li.setContentLookup(False)
    xbmcplugin.setResolvedUrl(handle, True, li)


# ── Public API ────────────────────────────────────────────────────────────────

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

    use_rd = _rd_ok()
    use_tb = _tb_ok()
    if not use_rd and not use_tb:
        _fail("No debrid service configured. Add Real Debrid or TorBox in Settings.")
        return

    # 1. Fetch TMDB metadata ──────────────────────────────────────────────────
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

    # 2. Build scraper payload ────────────────────────────────────────────────
    if item_type == "episode":
        scrape_data: dict[str, Any] = {
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

    # 3. Scrape ──────────────────────────────────────────────────────────────
    from services import cocoscrapers as cocos

    if not cocos.is_available():
        _fail("script.module.cocoscrapers is not installed.")
        return

    sources: list[dict[str, Any]] = []
    scrape_thread = Thread(target=lambda: sources.extend(cocos.scrape(scrape_data)), daemon=True)
    scrape_thread.start()

    progress = xbmcgui.DialogProgress()
    progress.create("Bacterio", f"Searching — {title}…")
    start = time.monotonic()

    while scrape_thread.is_alive():
        elapsed = time.monotonic() - start
        pct = min(int((elapsed / _SCRAPE_TIMEOUT) * 100), 99)
        progress.update(pct, f"Found {len(sources)} sources…")
        if progress.iscanceled():
            progress.close()
            _fail("Cancelled.")
            return
        xbmc.sleep(300)

    progress.update(100)
    progress.close()

    sources = [s for s in sources if len(s.get("hash", "")) == 40]
    if not sources:
        _fail(f"No sources found for {title}.")
        return

    # 4. Check instant availability across enabled providers ─────────────────
    hashes = list({s["hash"].lower() for s in sources})
    rd_cached: set[str] = set()
    tb_cached: set[str] = set()

    if use_rd:
        try:
            rd_cached = RealDebrid.check_instant_availability(hashes)
        except Exception as e:
            log(str(e), "resolve_and_play/rd_cache")

    if use_tb:
        try:
            tb_cached = TorBox.check_instant_availability(hashes)
        except Exception as e:
            log(str(e), "resolve_and_play/tb_cache")

    all_cached = rd_cached | tb_cached
    sorted_src = _sort_sources(sources, all_cached)
    auto_play = get_setting("playback.auto_play") == "true"

    # 5. Source selection ─────────────────────────────────────────────────────
    if auto_play:
        ordered = sorted_src
    else:
        source = _select_source(sorted_src, rd_cached, tb_cached, title)
        if source is None:
            xbmcplugin.setResolvedUrl(handle, False, xbmcgui.ListItem())
            return
        others = [s for s in sorted_src if s is not source]
        ordered = [source] + others

    # 6. Try sources with automatic fallback ─────────────────────────────────
    for i, src in enumerate(ordered):
        h = src.get("hash", "").lower()
        magnet = src.get("url") or f"magnet:?xt=urn:btih:{src['hash']}&dn={src.get('name', '')}"
        if i > 0:
            info(f"Source {i} failed — trying next ({i + 1}/{len(ordered)})…")

        # Prefer whichever provider has this hash cached; fall back to the other
        providers: list[str] = []
        if use_rd and h in rd_cached:
            providers.append("rd")
        if use_tb and h in tb_cached:
            providers.append("torbox")
        if not providers:
            if use_rd:
                providers.append("rd")
            if use_tb:
                providers.append("torbox")

        for provider in providers:
            direct_url = _add_to_rd(magnet, title) if provider == "rd" else _add_to_torbox(magnet, title)
            if direct_url:
                _tag_playing(item_type, tmdb_id, season, episode)
                _play_url(direct_url, handle)
                return

    _fail(f"All {len(ordered)} sources failed for {title}.")


def resolve_magnet_and_play(magnet: str, handle: int, title: str = "",
                            item_type: str = "movie", tmdb_id: str = "",
                            season: str = "", episode: str = "") -> None:
    """Resolve a single magnet directly — used when the caller already has a magnet URI."""
    use_rd = _rd_ok()
    use_tb = _tb_ok()
    if not use_rd and not use_tb:
        error("No debrid service configured.")
        xbmcplugin.setResolvedUrl(handle, False, xbmcgui.ListItem())
        return

    direct_url = _add_to_rd(magnet, title) if use_rd else _add_to_torbox(magnet, title)
    if not direct_url and use_rd and use_tb:
        direct_url = _add_to_torbox(magnet, title)

    if direct_url:
        if tmdb_id:
            _tag_playing(item_type, tmdb_id, season, episode)
        _play_url(direct_url, handle)
    else:
        error("Failed to resolve magnet via any debrid provider.")
        xbmcplugin.setResolvedUrl(handle, False, xbmcgui.ListItem())


# ── Helpers ───────────────────────────────────────────────────────────────────

def _select_source(
    sources: list[dict[str, Any]],
    rd_cached: set[str],
    tb_cached: set[str],
    title: str = "",
) -> dict[str, Any] | None:
    labels: list[str] = []
    for s in sources:
        h = s.get("hash", "").lower()
        tag = ""
        if h in rd_cached:
            tag += "[RD✓] "
        if h in tb_cached:
            tag += "[TB✓] "
        quality = s.get("quality", "?")
        size = s.get("size")
        size_str = f"  {size:.1f} GB" if isinstance(size, (int, float)) else ""
        is_cached = bool(tag)
        seeders = s.get("seeders")
        seed_str = f"  ↑{seeders}" if seeders and not is_cached else ""
        name = (s.get("name") or "")[:55]
        labels.append(f"{tag}{quality}{size_str}{seed_str}  {name}")

    idx = xbmcgui.Dialog().select(f"Sources — {title}", list(labels))
    if idx < 0:
        return None
    return sources[idx]


def _get_episode_title(show_id: int, season: int, episode: int) -> str:
    try:
        season_data = Tmdb.tv_season(show_id, season)
        for ep in season_data.get("episodes", []):
            if ep.get("episode_number") == episode:
                return ep.get("name", "")
    except Exception:
        pass
    return ""
