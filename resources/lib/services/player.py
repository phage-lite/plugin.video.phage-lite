import re
import time
import xbmc
import xbmcgui
import xbmcplugin
from threading import Thread
from typing import Any

from services.tmdb import Tmdb
from services.real_debrid import RealDebrid
from services.torbox import TorBox
from scrapers import torrentio as torrentio_scraper
from utils.notifications import error, info
from utils.logger import log
from settings.settings import get_setting

_SCRAPE_TIMEOUT = 20
_POLL_INTERVAL = 500  # ms
_RD_INITIAL_WAIT = 30  # seconds to wait for waiting_files_selection
_RD_DOWNLOAD_WAIT = 60  # seconds to wait for downloaded
_TB_DOWNLOAD_WAIT = 60  # seconds to wait for TorBox download
_TB_ERROR_STATES = {"error", "failed", "dead"}

_QUALITY_RANK = {
    "PREFERRED": 0,
    "4K": 1,
    "1080p": 2,
    "720p": 3,
    "SD": 4,
    "CAM": 5,
    "TELE": 5,
    "SYNC": 5,
}
_LANG_RANK = {
    "PREFERRED": 0,
    "EN": 1,
}
_RD_ERROR_STATUSES = {"magnet_error", "error", "dead", "virus"}


def _match_episode_file(
    files: list[dict[str, Any]], season: int, episode: int
) -> int | None:
    """Return the index into *files* that matches the requested season/episode, or None."""
    patterns = [
        rf"[Ss]{season:02d}[Ee]{episode:02d}",
        rf"[Ss]{season}[Ee]{episode:02d}",
        rf"\b{season}[xX]{episode:02d}\b",
    ]
    for i, f in enumerate(files):
        name = f.get("path") or f.get("name") or ""
        for pattern in patterns:
            if re.search(pattern, name):
                return i
    return None


# ── Internal helpers ──────────────────────────────────────────────────────────


def _rd_ok() -> bool:
    return RealDebrid.is_enabled and RealDebrid.is_authenticated


def _tb_ok() -> bool:
    return TorBox.is_enabled and TorBox.is_authenticated


def _sort_sources(
    sources: list[dict[str, Any]], cached: set[str]
) -> list[dict[str, Any]]:
    prefer_cached = get_setting("playback.prefer_cached")
    quality_pref = get_setting("playback.preferred_quality")
    lang_pref = get_setting("playback.preferred_lang")
    if prefer_cached == "0":
        # best quality, ignore cache order
        return sorted(
            sources,
            key=lambda s: (
                _LANG_RANK.get("PREFERRED" if s.get("language", "EN") == lang_pref else s.get("language", "EN"), 2),
                _QUALITY_RANK.get("PREFERRED" if s.get("quality", "SD") == quality_pref else s.get("quality", "SD"), 9),
                0 if s.get("hash", "").lower() in cached else 1,
                -int(s.get("seeders") or 0),
            ),
        )
    # default: cached first, then quality
    return sorted(
        sources,
        key=lambda s: (
            _LANG_RANK.get("PREFERRED" if s.get("language", "EN") == lang_pref else s.get("language", "EN"), 2),
            0 if s.get("hash", "").lower() in cached else 1,
            _QUALITY_RANK.get("PREFERRED" if s.get("quality", "SD") == quality_pref else s.get("quality", "SD"), 9),
            -int(s.get("seeders") or 0),
        ),
    )


def _add_to_rd(
    magnet: str,
    title: str,
    season: int | None = None,
    episode: int | None = None,
) -> str:
    """
    Add a magnet to RealDebrid and wait for a streamable URL.
    Returns the direct URL on success, or '' on any failure (error status,
    timeout, cancellation). Never calls setResolvedUrl itself.
    """
    progress = xbmcgui.DialogProgress()
    progress.create("Bacterio", f"Opening - {title}…" if title else "Opening…")

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
                progress.close()
                return "Cancel"
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

        if info_data.get("status") == "downloaded":
            # Already cached — pick the right file from the existing links
            links: list[str] = info_data.get("links", [])
            if not links:
                return ""
            link = _pick_rd_link(info_data, links, season, episode)
            result = RealDebrid.unrestrict_link(link)
            return result.get("download") or result.get("url") or ""

        # waiting_files_selection — select the specific episode file if possible
        file_ids = _find_rd_file_id(info_data, season, episode)
        RealDebrid.select_files(torrent_id, file_ids)

        deadline = time.monotonic() + _RD_DOWNLOAD_WAIT
        while time.monotonic() < deadline:
            xbmc.sleep(_POLL_INTERVAL)
            if progress.iscanceled():
                progress.close()
                return "Cancel"
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

        links = info_data.get("links", [])
        if not links:
            return ""

        result = RealDebrid.unrestrict_link(links[0])
        return result.get("download") or result.get("url") or ""

    except Exception as e:
        log(str(e), "_add_to_rd")
        return ""
    finally:
        progress.close()


def _find_rd_file_id(
    info_data: dict[str, Any], season: int | None, episode: int | None
) -> str:
    """Return a comma-separated file ID string to pass to select_files, or 'all'."""
    if season is None or episode is None:
        return "all"
    files: list[dict[str, Any]] = info_data.get("files", [])
    idx = _match_episode_file(files, season, episode)
    if idx is not None:
        file_id = files[idx].get("id")
        if file_id:
            return str(file_id)
    return "all"


def _pick_rd_link(
    info_data: dict[str, Any],
    links: list[str],
    season: int | None,
    episode: int | None,
) -> str:
    """Pick the correct download link from an already-downloaded RD torrent."""
    if season is None or episode is None or len(links) <= 1:
        return links[0]
    files: list[dict[str, Any]] = info_data.get("files", [])
    selected = [f for f in files if f.get("selected")]
    idx = _match_episode_file(selected, season, episode)
    if idx is not None and idx < len(links):
        return links[idx]
    return links[0]


def _add_to_torbox(
    magnet: str,
    title: str,
    season: int | None = None,
    episode: int | None = None,
    is_cached: bool = False,
) -> str:
    progress = xbmcgui.DialogProgress()
    progress.create("Bacterio", f"Opening - {title}…" if title else "Opening…")
    log(f"{title}, {season}x{episode} cached:{is_cached}", "_add_to_torbox")

    try:
        result = TorBox.add(magnet, is_cached)
        log(f"{result}", "add_magnet")
        if not result.get("success"):
            log(f"TorBox add_magnet failed: {result}", "_add_to_torbox")
            return ""

        data = result.get("data")
        if data is None:
            return ""

        torrent_id: int = data.get("torrent_id")
        if not torrent_id:
            return ""

        status_data: dict[str, Any] = {}
        deadline = time.monotonic() + _TB_DOWNLOAD_WAIT
        while time.monotonic() < deadline:
            xbmc.sleep(_POLL_INTERVAL)
            if progress.iscanceled():
                progress.close()
                return "Cancel"
            torrent_status = TorBox.get_torrent_status(torrent_id)
            log(f"{torrent_status}", "wait_for_download")
            status_data = torrent_status.get("data", {})
            state: str = status_data.get("download_state", "")
            pct = int(float(status_data.get("progress", 0)) * 100)
            progress.update(pct, f"TorBox: {state}")
            if state in _TB_ERROR_STATES:
                log(f"TorBox error state: {state}", "_add_to_torbox")
                return ""
            if state in ("cached", "completed", "uploading", "seeding"):
                break
        else:
            log("TorBox timed out", "_add_to_torbox")
            return ""

        files: list[dict[str, Any]] = status_data.get("files") or []
        target = TorBox.pick_video_file(files, season=season, episode=episode)
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
    log(direct_url, "play_url")
    li.setContentLookup(False)
    xbmcplugin.setResolvedUrl(handle, True, li)


# ── Public API ────────────────────────────────────────────────────────────────


def resolve_and_play(
    item_type: str,
    tmdb_id: str,
    handle: int,
    season: str = "",
    episode: str = "",
    force_select: bool = False,
    scraper_filter: str = "",
):
    def _fail(msg: str):
        log(msg, "resolve_and_play")
        error(msg)
        xbmcplugin.setResolvedUrl(handle, False, xbmcgui.ListItem())

    use_rd = _rd_ok()
    use_tb = _tb_ok()
    log(
        f"use_tb={use_tb} use_rd={use_rd} type={item_type} id={tmdb_id} s={season} e={episode}",
        "resolve_and_play",
    )
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
        else:
            ext = Tmdb.movie_external_ids(int(tmdb_id))
            details = Tmdb.movie_details(int(tmdb_id))
            title = details.get("title", "")
            year = (details.get("release_date") or "")[:4]
    except Exception as e:
        log(str(e), "resolve_and_play/tmdb")
        _fail("Could not fetch metadata from TMDB.")
        return

    imdb_id = ext.get("imdb_id") or ""
    log(f"title={title!r} year={year} imdb={imdb_id}", "resolve_and_play")
    if not imdb_id:
        _fail("No IMDB ID found for this title.")
        return

    # 2. Build scraper payload ────────────────────────────────────────────────
    if item_type == "episode":
        scrape_data: dict[str, Any] = {
            "tvshowtitle": title,
            "title": title,  # show title - scrapers use this as the primary search key
            "year": year,
            "imdb": imdb_id,
            "season": int(season),
            "episode": int(episode),
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

    use_torrentio = scraper_filter == "torrentio" or (
        not scraper_filter and get_setting("scrapers.torrentio") != "false"
    )
    use_cocos = (
        scraper_filter == "cocoscrapers"
        or (not scraper_filter and get_setting("scrapers.cocoscrapers") != "false")
    ) and cocos.is_available()

    sources: list[dict[str, Any]] = []
    torrentio_sources: list[dict[str, Any]] = []

    def _run_torrentio() -> None:
        if item_type == "episode":
            torrentio_sources.extend(
                torrentio_scraper.scrape(imdb_id, int(season), int(episode))
            )
        else:
            torrentio_sources.extend(torrentio_scraper.scrape(imdb_id))

    torrentio_thread: Thread | None = None
    if use_torrentio:
        torrentio_thread = Thread(target=_run_torrentio, daemon=True)
        torrentio_thread.start()

    if use_cocos:
        scrape_thread: Thread | None = Thread(
            target=lambda: sources.extend(cocos.scrape(scrape_data)), daemon=True
        )
        scrape_thread.start()
    else:
        scrape_thread = None

    progress = xbmcgui.DialogProgress()
    progress.create("Bacterio", f"Searching - {title}…")
    start = time.monotonic()

    active = scrape_thread
    while active and active.is_alive():
        elapsed = time.monotonic() - start
        pct = min(int((elapsed / _SCRAPE_TIMEOUT) * 100), 99)
        progress.update(pct, f"Found {len(sources) + len(torrentio_sources)} sources…")
        if progress.iscanceled():
            progress.close()
            _fail("Cancelled.")
            return
        xbmc.sleep(300)

    if torrentio_thread:
        torrentio_thread.join(
            timeout=max(0.0, _SCRAPE_TIMEOUT - (time.monotonic() - start))
        )

    progress.update(100)
    progress.close()

    # Merge: cocoscrapers first, then any new hashes from Torrentio
    seen: set[str] = {s.get("hash", "").lower() for s in sources}
    for s in torrentio_sources:
        h = s.get("hash", "").lower()
        if h and h not in seen:
            sources.append(s)
            seen.add(h)

    log(f"raw sources={len(sources)}", "resolve_and_play")
    raw_sources = sources[:]
    sources = [s for s in sources if len(s.get("hash", "")) == 40]
    # Also accept sources whose hash is embedded in the magnet URL
    if not sources:

        def _with_hash(s: dict[str, Any]) -> dict[str, Any] | None:
            url = s.get("url", "")
            lower = url.lower()
            if "btih:" in lower:
                h = url[lower.index("btih:") + 5 :].split("&")[0]
                if len(h) == 40:
                    return {**s, "hash": h}
            return None

        sources = [h for s in raw_sources if (h := _with_hash(s)) is not None]

    log(f"filtered sources={len(sources)}", "resolve_and_play")
    if not sources:
        _fail(f"No sources found for {title}.")
        return

    # 4. Check instant availability across enabled providers ─────────────────
    hashes = list({s["hash"].lower() for s in sources})
    tb_cached: set[str] = set()

    if use_tb:
        try:
            tb_cached = TorBox.check_instant_availability(hashes)
        except Exception as e:
            log(str(e), "resolve_and_play/tb_cache")

    all_cached = tb_cached
    sorted_src = _sort_sources(sources, all_cached)
    auto_play = not force_select and get_setting("playback.auto_play") == "true"

    # 5. Source selection ─────────────────────────────────────────────────────
    if auto_play:
        ordered = sorted_src
    else:
        source = _select_source(sorted_src, tb_cached, title)
        if source is None:
            xbmcplugin.setResolvedUrl(handle, False, xbmcgui.ListItem())
            return
        others = [s for s in sorted_src if s is not source]
        ordered = [source] + others

    # 6. Try sources with automatic fallback ─────────────────────────────────
    for i, src in enumerate(ordered):
        h = src.get("hash", "").lower()
        magnet = (
            src.get("url")
            or f"magnet:?xt=urn:btih:{src['hash']}&dn={src.get('name', '')}"
        )
        log(str(src), "try_source")

        # Prefer whichever provider has this hash cached; fall back to the other
        providers: list[str] = []
        is_cached = h in all_cached
        if use_tb and h in tb_cached:
            providers.append("torbox")
        if not providers:
            if use_tb:
                providers.append("torbox")
            if use_rd:
                providers.append("rd")

        ep_season = int(season) if season else None
        ep_episode = int(episode) if episode else None
        for provider in providers:
            direct_url = (
                _add_to_rd(magnet, title, season=ep_season, episode=ep_episode)
                if provider == "rd"
                else _add_to_torbox(
                    magnet,
                    title,
                    season=ep_season,
                    episode=ep_episode,
                    is_cached=is_cached,
                )
            )
            if direct_url and direct_url != "Cancel":
                _tag_playing(item_type, tmdb_id, season, episode)
                _play_url(direct_url, handle)
                return
            elif direct_url == "Cancel":
                _fail("Cancelled")
                return
            elif i < len(ordered):
                info(f"Source {i + 1} failed - trying next ({i + 1}/{len(ordered)})…")

    _fail(f"All {len(ordered)} sources failed for {title}.")


def resolve_magnet_and_play(
    magnet: str,
    handle: int,
    title: str = "",
    item_type: str = "movie",
    tmdb_id: str = "",
    season: str = "",
    episode: str = "",
) -> None:
    """Resolve a single magnet directly - used when the caller already has a magnet URI."""
    use_rd = _rd_ok()
    use_tb = _tb_ok()
    if not use_rd and not use_tb:
        error("No debrid service configured.")
        xbmcplugin.setResolvedUrl(handle, False, xbmcgui.ListItem())
        return

    direct_url = _add_to_torbox(magnet, title) if use_tb else _add_to_rd(magnet, title)
    if not direct_url and use_rd and use_tb:
        direct_url = _add_to_rd(magnet, title)

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
    cached: set[str],
    title: str = "",
) -> dict[str, Any] | None:
    labels: list[str] = []
    for s in sources:
        h = s.get("hash", "").lower()
        tag = ""
        if h in cached:
            tag += "[Cached✓] "
        quality = s.get("quality", "?")
        size = s.get("size")
        size_str = f"  {size:.1f} GB" if isinstance(size, (int, float)) else ""
        is_cached = bool(tag)
        seeders = s.get("seeders")
        seed_str = f"  ↑{seeders}" if seeders and not is_cached else ""
        name = (s.get("name") or "")[:55]
        labels.append(f"{tag}{quality}{size_str}{seed_str}  {name}")

    idx = xbmcgui.Dialog().select(f"Sources - {title}", list(labels))
    if idx < 0:
        return None
    return sources[idx]
