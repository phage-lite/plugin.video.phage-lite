import sys
import time
import xbmcaddon
from threading import Thread, Lock

from utils.logger import log

_ADDON_ID = "script.module.cocoscrapers"
_SCRAPE_TIMEOUT = 20


def is_available() -> bool:
    try:
        xbmcaddon.Addon(_ADDON_ID)
        return True
    except Exception:
        return False


def _inject_path() -> bool:
    try:
        root = xbmcaddon.Addon(_ADDON_ID).getAddonInfo("path")
        lib = f"{root}/lib"
        if lib not in sys.path:
            sys.path.insert(0, lib)
        return True
    except Exception as e:
        log(str(e), "_inject_path")
        return False


def scrape(data: dict, timeout: int = _SCRAPE_TIMEOUT) -> list:
    """
    Run all enabled cocoscrapers in parallel and return combined sources.

    data for movies:
        {'title': str, 'year': str, 'imdb': str, 'aliases': []}

    data for episodes:
        {'tvshowtitle': str, 'title': str, 'year': str, 'imdb': str,
         'season': str, 'episode': str, 'aliases': []}

    Each returned source dict has at minimum:
        hash (str, 40-char hex), url (magnet str), quality (str), seeders (int)
    """
    if not _inject_path():
        return []

    try:
        import cocoscrapers
        source_modules = cocoscrapers.sources()
    except Exception as e:
        log(str(e), "scrape")
        return []

    if not source_modules:
        return []

    all_sources: list = []
    lock = Lock()

    def _run(name: str, cls):
        try:
            results = cls().sources(data, []) or []
            with lock:
                all_sources.extend(results)
        except Exception as e:
            log(f"{name}: {e}", "scrape")

    threads = [
        Thread(target=_run, args=(name, cls), daemon=True)
        for name, cls in source_modules
    ]
    for t in threads:
        t.start()

    deadline = time.monotonic() + timeout
    for t in threads:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        t.join(timeout=max(remaining, 0))

    return all_sources


def pick_best_cached(sources: list, cached_hashes: set) -> str:
    """Return the magnet URL of the best quality RD-cached source, or ''."""
    candidates = [
        s for s in sources
        if s.get("hash", "").lower() in cached_hashes
    ]
    if not candidates:
        return ""

    _RANK = {"4K": 0, "1080p": 1, "720p": 2, "SD": 3, "CAM": 4, "TELE": 5, "SYNC": 5}
    candidates.sort(key=lambda s: (
        _RANK.get(s.get("quality", "SD"), 9),
        -int(s.get("seeders") or 0),
    ))

    best = candidates[0]
    url = best.get("url") or ""
    if not url:
        h = best.get("hash", "")
        name = best.get("name", "")
        url = f"magnet:?xt=urn:btih:{h}&dn={name}" if h else ""
    return url
