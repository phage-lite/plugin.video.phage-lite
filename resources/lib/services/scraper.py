"""Scraper backend registry.

To add a new backend: implement `ScraperBackend` and append an instance to
`BACKENDS`. Nothing else in the codebase needs to change - `player.py` only
ever talks to this module. See docs/adr/0001-scraper-backend-interface.md.
"""

import time
from threading import Lock, Thread
from typing import Callable

from services.magneto import Magneto
from utils.types import ScrapePayload, ScraperBackend, SourceResult
from utils.logger import err

_SCRAPE_TIMEOUT = 20

BACKENDS: list[ScraperBackend] = [Magneto()]


def scrape(
    payload: ScrapePayload,
    timeout: int = _SCRAPE_TIMEOUT,
    on_result: Callable[[SourceResult], None] | None = None,
) -> list[SourceResult]:
    """Query every available backend concurrently and return their combined results.

    If given, *on_result* is called for each source as soon as any backend finds it.
    """
    active = [b for b in BACKENDS if b.is_available()]
    if not active:
        return []

    results: list[SourceResult] = []
    lock = Lock()

    def _run(backend: ScraperBackend) -> None:
        try:
            found = backend.scrape(payload, timeout, on_result) or []
            with lock:
                results.extend(found)
        except Exception as e:
            err(f"{type(backend).__name__}: {e}", "scrape")

    threads = [Thread(target=_run, args=(b,), daemon=True) for b in active]
    for t in threads:
        t.start()

    deadline = time.monotonic() + timeout
    for t in threads:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        t.join(timeout=max(remaining, 0))

    return results
