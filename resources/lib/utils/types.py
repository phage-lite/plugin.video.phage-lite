from enum import Enum
from typing import Protocol
from typing_extensions import NotRequired, TypedDict


class ItemType(Enum):
    MOVIE = "movie"
    SHOW = "show"


class MovieScrapePayload(TypedDict):
    """Sent to a ScraperBackend's `scrape()` when searching for a movie."""

    title: str
    year: str
    imdb: str
    aliases: list[str]


class EpisodeScrapePayload(TypedDict):
    """Sent to a ScraperBackend's `scrape()` when searching for an episode.

    The same payload covers both single-episode and season/show-pack results -
    a backend decides internally whether and how to search packs.
    """

    tvshowtitle: str
    title: str
    year: str
    imdb: str
    season: int
    episode: int
    aliases: list[str]


ScrapePayload = MovieScrapePayload | EpisodeScrapePayload


class SourceResult(TypedDict):
    """A single normalized torrent/magnet candidate returned by a ScraperBackend."""

    provider: str
    source: str
    hash: str
    url: str
    name: str
    quality: str
    language: str
    seeders: int
    size: float
    debridonly: bool
    # Only present on season/show-pack results:
    package: NotRequired[str]  # "season" | "show"
    episode_start: NotRequired[int]  # partial season pack range
    episode_end: NotRequired[int]
    last_season: NotRequired[int]  # show pack: last season included


class ScraperBackend(Protocol):
    """A pluggable source of torrent/magnet candidates.

    Add a new backend by implementing this shape and appending an instance to
    the registry in `services/scraper.py` - nothing else needs to change.
    See docs/adr/0001-scraper-backend-interface.md.
    """

    def is_available(self) -> bool:
        """Whether this backend's dependencies are installed and usable right now."""
        ...

    def scrape(self, payload: ScrapePayload, timeout: int) -> list[SourceResult]:
        """Search for sources matching *payload*, waiting at most *timeout* seconds."""
        ...

