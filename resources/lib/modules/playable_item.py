from abc import ABC, abstractmethod
from xbmcgui import ListItem

from types.types import Scrapers


class PlayableItem(ABC):
    def __init__(
        self,
        label: str
    ) -> None:
        self.listItem: ListItem = ListItem(label)

        self.listItem.addContextMenuItems(
            [
                ("Mark as Watched", f"RunPlugin({self.get_mark_watched_url()})"),
                ("Select Source", f"PlayMedia({self.get_select_source_url()})"),
                (
                    "Scrape with Torrentio",
                    f"PlayMedia({self.get_scrape_with_url(Scrapers.TORRENTIO)})",
                ),
                (
                    "Scrape with CocoScrapers",
                    f"PlayMedia({self.get_scrape_with_url(Scrapers.COCO)})",
                ),
            ]
        )

    @abstractmethod
    def get_mark_watched_url(self) -> str: ...

    @abstractmethod
    def get_scrape_with_url(self, scraper: Scrapers) -> str: ...

    @abstractmethod
    def get_select_source_url(self) -> str: ...

    @abstractmethod
    def get_play_url(self) -> str: ...
