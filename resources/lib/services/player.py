import re
import time
from typing import Any, Literal, NamedTuple
from typing_extensions import cast
import xbmc
import xbmcgui
import xbmcplugin
from threading import Thread

from services.tmdb import Tmdb
from services.real_debrid import RealDebrid
from services.torbox import TorBox
from services import scraper
from utils.types import EpisodeScrapePayload, MovieScrapePayload, ScrapePayload, SourceResult
from utils.notifications import error, info
from utils.logger import debug, err, log, warn
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


class ScrapeCancelled(Exception):
    """Raised when the user cancels the progress dialog while sources are still coming in."""


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
    sources: list[SourceResult], cached: set[str]
) -> list[SourceResult]:
    prefer_cached = get_setting("playback.prefer_cached")
    quality_pref = get_setting("playback.preferred_quality")
    lang_pref = get_setting("playback.preferred_lang")
    if prefer_cached == "0":
        # best quality, ignore cache order
        return sorted(
            sources,
            key=lambda s: (
                _LANG_RANK.get(
                    "PREFERRED" if s.get("language", "EN") == lang_pref else s.get("language", "EN"),
                    2,
                ),
                _QUALITY_RANK.get(
                    "PREFERRED" if s.get("quality", "SD") == quality_pref else s.get("quality", "SD"),
                    9,
                ),
                0 if s.get("hash", "").lower() in cached else 1,
                -int(s.get("seeders") or 0),
            ),
        )
    # default: cached first, then quality
    return sorted(
        sources,
        key=lambda s: (
            _LANG_RANK.get(
                "PREFERRED" if s.get("language", "EN") == lang_pref else s.get("language", "EN"),
                2,
            ),
            0 if s.get("hash", "").lower() in cached else 1,
            _QUALITY_RANK.get(
                "PREFERRED" if s.get("quality", "SD") == quality_pref else s.get("quality", "SD"),
                9,
            ),
            -int(s.get("seeders") or 0),
        ),
    )


def _add_to_rd(
    progress: xbmcgui.DialogProgress,
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
    progress.update(0, f"Opening - {title}…" if title else "Opening…")

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
                warn(f"RD torrent error: {status}", "_add_to_rd")
                return ""
            if status in ("waiting_files_selection", "downloaded"):
                break
        else:
            warn("RD timed out waiting for file selection", "_add_to_rd")
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
                warn(f"RD download error: {status}", "_add_to_rd")
                return ""
            if status == "downloaded":
                break
        else:
            warn("RD timed out waiting for download", "_add_to_rd")
            return ""

        links = info_data.get("links", [])
        if not links:
            return ""

        result = RealDebrid.unrestrict_link(links[0])
        return result.get("download") or result.get("url") or ""

    except Exception as e:
        err(str(e), "_add_to_rd")
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
    progress: xbmcgui.DialogProgress,
    magnet: str,
    title: str,
    season: int | None = None,
    episode: int | None = None,
    is_cached: bool = False,
) -> str:
    progress.update(0, f"Opening - {title}…" if title else "Opening…")
    debug(f"{title}, {season}x{episode} cached:{is_cached}", "_add_to_torbox")

    try:
        result = TorBox.add(magnet, is_cached)
        debug(f"{result}", "add_magnet")
        if not result.get("success"):
            warn(f"TorBox add_magnet failed: {result}", "_add_to_torbox")
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
            debug(f"{torrent_status}", "wait_for_download")
            status_data = torrent_status.get("data", {})
            state: str = status_data.get("download_state", "")
            pct = int(float(status_data.get("progress", 0)) * 100)
            progress.update(pct, f"TorBox: {state}")
            if state in _TB_ERROR_STATES:
                warn(f"TorBox error state: {state}", "_add_to_torbox")
                return ""
            if state in ("cached", "completed", "uploading", "seeding"):
                break
        else:
            warn("TorBox timed out", "_add_to_torbox")
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
        err(str(e), "_add_to_torbox")
        return ""
    finally:
        progress.close()


def _tag_playing(item_type: str, tmdb_id: str, season: str, episode: str) -> None:
    debug(f"type={item_type} id={tmdb_id} season={season} ep={episode}", "_tag_playing")
    win = xbmcgui.Window(10000)
    win.setProperty("bacterio.type", item_type)
    win.setProperty("bacterio.tmdb_id", tmdb_id)
    win.setProperty("bacterio.season", season)
    win.setProperty("bacterio.episode", episode)


def _play_url(
    direct_url: str, handle: int, media_type: str, metadata: dict[str, Any] = {}
):
    title = metadata.get("title", "")
    listItem = xbmcgui.ListItem(
        label=metadata.get("title", ""),
        label2=metadata.get("title", ""),
        path=direct_url,
    )
    tag = cast(xbmc.InfoTagVideo, listItem.getVideoInfoTag())
    tag.setMediaType(media_type)
    tag.setTitle(title)
    tag.setOriginalTitle(title)
    if media_type == "episode":
        tag.setTvShowTitle(metadata.get("showtitle", ""))
        tag.setSeason(metadata.get("season", -1))
        tag.setEpisode(metadata.get("episode", -1))
    tag.setPlot(metadata.get("overview", ""))
    tag.setDuration(int(metadata.get("runtime") or 30) * 60)
    tag.setRating(float(metadata.get("vote_average", 0)))
    tag.setFirstAired(metadata.get("firstaired", ""))
    listItem.setArt(metadata.get("art", {}))
    debug(direct_url, "play_url")
    listItem.setContentLookup(False)
    xbmcplugin.setResolvedUrl(handle, True, listItem)


# ── Scraping ───────────────────────────────────────────────────────────────


class _TitleInfo(NamedTuple):
    title: str
    year: str
    imdb_id: str


def _fetch_metadata(item_type: str, tmdb_id: str) -> _TitleInfo:
    """Look up title, year and IMDB id from TMDB for a movie or show."""
    if item_type == "episode":
        ext = Tmdb.tv_external_ids(int(tmdb_id))
        details = Tmdb.tv_show_details(int(tmdb_id))
        title = details.get("name", "")
        year = (details.get("first_air_date") or "")[:4]
    else:
        ext = Tmdb.movie_external_ids(int(tmdb_id))
        details = Tmdb.movie_details(int(tmdb_id))
        title = details.get("title", "")
        year = (details.get("release_date") or "")[:4]
    return _TitleInfo(title=title, year=year, imdb_id=ext.get("imdb_id") or "")


def _build_payload(
    meta: _TitleInfo, item_type: str, season: str, episode: str
) -> ScrapePayload:
    """Build the payload Magneto's providers expect for a scrape() call."""
    if item_type == "episode":
        return EpisodeScrapePayload(
            tvshowtitle=meta.title,
            title=meta.title,
            year=meta.year,
            imdb=meta.imdb_id,
            season=int(season),
            episode=int(episode),
            aliases=[],
        )
    return MovieScrapePayload(
        title=meta.title, year=meta.year, imdb=meta.imdb_id, aliases=[]
    )


def get_sources(
    payload: ScrapePayload,
    progress: xbmcgui.DialogProgress,
    timeout: int = _SCRAPE_TIMEOUT,
) -> list[SourceResult]:
    """Run the Magneto scrape in a background thread while driving *progress*.

    Raises ScrapeCancelled if the user cancels before the scrape completes.
    """
    sources: list[SourceResult] = []
    scrape_thread = Thread(
        target=lambda: sources.extend(scraper.scrape(payload, timeout)), daemon=True
    )
    scrape_thread.start()

    start = time.monotonic()
    while scrape_thread.is_alive():
        elapsed = time.monotonic() - start
        pct = min(int((elapsed / timeout) * 100), 99)
        progress.update(pct, f"Found {len(sources)} sources…")
        if progress.iscanceled():
            raise ScrapeCancelled()
        xbmc.sleep(300)

    progress.update(100)
    return sources


def _check_availability(hashes: list[str], use_tb: bool) -> set[str]:
    if not use_tb:
        return set()
    try:
        return TorBox.check_instant_availability(hashes)
    except Exception as e:
        err(str(e), "_check_availability")
        return set()


# ── Playback ─────────────────────────────────────────────────────────────────

_TryOutcome = Literal["played", "cancelled", "exhausted"]


def _try_sources(
    ordered: list[SourceResult],
    cached: set[str],
    use_rd: bool,
    use_tb: bool,
    item_type: str,
    tmdb_id: str,
    handle: int,
    season: str,
    episode: str,
    title: str,
    progress: xbmcgui.DialogProgress,
    metadata: dict[str, Any],
) -> _TryOutcome:
    """Try each source in order, falling back to the next on failure."""
    ep_season = int(season) if season else None
    ep_episode = int(episode) if episode else None

    for i, src in enumerate(ordered):
        h = src["hash"]
        magnet = src["url"]
        debug(str(src), "try_source")

        is_cached = h in cached
        providers: list[str] = []
        if use_tb and is_cached:
            providers.append("torbox")
        if not providers:
            if use_tb:
                providers.append("torbox")
            if use_rd:
                providers.append("rd")

        for provider in providers:
            direct_url = (
                _add_to_rd(progress, magnet, title, season=ep_season, episode=ep_episode)
                if provider == "rd"
                else _add_to_torbox(
                    progress,
                    magnet,
                    title,
                    season=ep_season,
                    episode=ep_episode,
                    is_cached=is_cached,
                )
            )
            if direct_url and direct_url != "Cancel":
                _tag_playing(item_type, tmdb_id, season, episode)
                _play_url(direct_url, handle, item_type, metadata)
                return "played"
            if direct_url == "Cancel":
                return "cancelled"
            info(f"Source {i + 1} failed - trying next ({i + 1}/{len(ordered)})…")

    return "exhausted"


# ── Public API ────────────────────────────────────────────────────────────────


def resolve_and_play(
    item_type: str,
    tmdb_id: str,
    handle: int,
    season: str = "",
    episode: str = "",
    force_select: bool = False,
    metadata: dict[str, Any] = {},
):
    def _fail(msg: str):
        err(msg, "resolve_and_play")
        error(msg)
        xbmcplugin.setResolvedUrl(handle, False, xbmcgui.ListItem())

    use_rd = _rd_ok()
    use_tb = _tb_ok()
    debug(
        f"use_tb={use_tb} use_rd={use_rd} type={item_type} id={tmdb_id} s={season} e={episode}",
        "resolve_and_play",
    )
    if not use_rd and not use_tb:
        _fail("No debrid service configured. Add Real Debrid or TorBox in Settings.")
        return

    try:
        meta = _fetch_metadata(item_type, tmdb_id)
    except Exception as e:
        err(str(e), "resolve_and_play/tmdb")
        _fail("Could not fetch metadata from TMDB.")
        return

    debug(f"title={meta.title!r} year={meta.year} imdb={meta.imdb_id}", "resolve_and_play")
    if not meta.imdb_id:
        _fail("No IMDB ID found for this title.")
        return

    payload = _build_payload(meta, item_type, season, episode)

    progress = xbmcgui.DialogProgress()
    progress.create("Bacterio", f"Searching - {meta.title}…")

    try:
        sources = get_sources(payload, progress)
    except ScrapeCancelled:
        progress.close()
        _fail("Cancelled.")
        return

    if not sources:
        progress.close()
        _fail(f"No sources found for {meta.title}.")
        return

    hashes = list({s["hash"] for s in sources})
    cached = _check_availability(hashes, use_tb)

    sorted_src = _sort_sources(sources, cached)
    auto_play = not force_select and get_setting("playback.auto_play") == "true"

    if auto_play:
        ordered = sorted_src
    else:
        source = _select_source(sorted_src, cached, meta.title)
        if source is None:
            progress.close()
            xbmcplugin.setResolvedUrl(handle, False, xbmcgui.ListItem())
            return
        others = [s for s in sorted_src if s is not source]
        ordered = [source] + others

    outcome = _try_sources(
        ordered,
        cached,
        use_rd,
        use_tb,
        item_type,
        tmdb_id,
        handle,
        season,
        episode,
        meta.title,
        progress,
        metadata,
    )
    if outcome == "cancelled":
        _fail("Cancelled")
    elif outcome == "exhausted":
        _fail(f"All {len(ordered)} sources failed for {meta.title}.")


def _select_source(
    sources: list[SourceResult],
    cached: set[str],
    title: str = "",
) -> SourceResult | None:
    labels: list[str] = []
    for s in sources:
        h = s.get("hash", "").lower()
        is_cached = h in cached
        tag = "[Cached] " if is_cached else ""
        package = s.get("package")
        if package == "show":
            tag += "[Show Pack] "
        elif package == "season":
            tag += "[Pack] "
        quality = s.get("quality", "?")
        size = s.get("size")
        size_str = f"  {size:.1f} GB" if isinstance(size, (int, float)) else ""
        seeders = s.get("seeders")
        seed_str = f"  Seeders: {seeders}" if seeders and not is_cached else ""
        name = (s.get("name") or "")[:55]
        labels.append(f"{tag}{quality}{size_str}{seed_str}  {name}")

    idx = xbmcgui.Dialog().select(f"Sources - {title}", list(labels))
    if idx < 0:
        return None
    return sources[idx]
