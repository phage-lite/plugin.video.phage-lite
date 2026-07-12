"""Magneto ScraperBackend implementation.

script.module.magneto ships a set of provider modules, each exposing a
`source` class with `.sources(payload, hostDict)` (single movie/episode) and,
for pack-capable providers, `.sources_packs(payload, hostDict)` (season packs).
We call every enabled provider concurrently, normalize whatever they hand
back into `SourceResult`, and return one flat list.
"""

import importlib
import sys
import time
from threading import Lock, Thread
from typing import Any, Callable

import xbmcaddon

from utils.types import ScrapePayload, SourceResult
from utils.logger import err

_ADDON_ID = "script.module.magneto"
_HASH_LENGTH = 40

# A provider's `.sources(payload, hostDict)` / `.sources_packs(payload, hostDict)` -
# both return a raw list of provider-specific dicts (or None on internal failure).
_ProviderCall = Callable[[ScrapePayload, list[Any]], list[dict[str, Any]] | None]


def _inject_path() -> bool:
    try:
        root = xbmcaddon.Addon(_ADDON_ID).getAddonInfo("path")
        lib = f"{root}/lib"
        if lib not in sys.path:
            sys.path.insert(0, lib)
        return True
    except Exception as e:
        err(str(e), "_inject_path")
        return False


def _providers(is_episode: bool) -> list[tuple[str, type]]:
    """Every enabled Magneto provider that supports this media type."""
    magneto = importlib.import_module("magneto")
    all_providers: list[tuple[str, type]] = magneto.sources()
    attr = "hasEpisodes" if is_episode else "hasMovies"
    return [(name, cls) for name, cls in all_providers if getattr(cls, attr, True)]


def _extract_hash(raw: dict[str, Any]) -> str:
    """A 40-char infohash, from the 'hash' field or parsed out of the magnet URL."""
    h = (raw.get("hash") or "").lower()
    if len(h) == _HASH_LENGTH:
        return h
    url = (raw.get("url") or "").lower()
    if "btih:" in url:
        h = url.split("btih:", 1)[1].split("&")[0]
        if len(h) == _HASH_LENGTH:
            return h
    return ""


def _normalize(raw: dict[str, Any]) -> SourceResult | None:
    h = _extract_hash(raw)
    if not h:
        return None

    result: SourceResult = {
        "provider": raw.get("provider", ""),
        "source": raw.get("source", "torrent"),
        "hash": h,
        "url": raw.get("url") or f"magnet:?xt=urn:btih:{h}&dn={raw.get('name', '')}",
        "name": raw.get("name", ""),
        "quality": raw.get("quality") or "SD",
        "language": (raw.get("language") or "EN").upper(),
        "seeders": int(raw.get("seeders") or 0),
        "size": float(raw.get("size") or 0),
        "debridonly": bool(raw.get("debridonly", True)),
    }
    for key in ("package", "episode_start", "episode_end", "last_season"):
        if key in raw:
            result[key] = raw[key]  # type: ignore[literal-required]
    return result


class Magneto:
    """ScraperBackend wrapping script.module.magneto's provider modules."""

    def is_available(self) -> bool:
        try:
            _ = xbmcaddon.Addon(_ADDON_ID)
            return True
        except Exception:
            return False

    def scrape(self, payload: ScrapePayload, timeout: int) -> list[SourceResult]:
        """Query every enabled provider concurrently and return normalized results.

        Episode payloads also trigger each pack-capable provider's season-pack
        search (`sources_packs`) alongside the single-episode search - the debrid
        layer matches the right file out of a pack by season/episode once it's added.
        """
        if not _inject_path():
            return []

        is_episode = "season" in payload
        try:
            providers = _providers(is_episode)
        except Exception as e:
            err(str(e), "scrape")
            return []

        raw_results: list[dict[str, Any]] = []
        lock = Lock()

        def _run(name: str, fn: _ProviderCall, host_dict: list[Any]) -> None:
            try:
                results = fn(payload, host_dict) or []
                with lock:
                    raw_results.extend(results)
            except Exception as e:
                err(f"{name}: {e}", "scrape")

        threads: list[Thread] = []
        for name, cls in providers:
            instance = cls()
            threads.append(Thread(target=_run, args=(name, instance.sources, []), daemon=True))
            if is_episode and getattr(instance, "pack_capable", False):
                threads.append(
                    Thread(
                        target=_run,
                        args=(f"{name}:packs", instance.sources_packs, []),
                        daemon=True,
                    )
                )

        for t in threads:
            t.start()

        deadline = time.monotonic() + timeout
        for t in threads:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            t.join(timeout=max(remaining, 0))

        return [n for raw in raw_results if (n := _normalize(raw)) is not None]
