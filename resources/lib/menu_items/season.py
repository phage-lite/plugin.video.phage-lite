from typing import Any
import xbmc
import xbmcgui

from services.tmdb import Tmdb
from utils.router import url

from menu_items.menu_item import MenuItem


class SeasonItem(MenuItem):
    def __init__(
        self,
        season_details: dict[str, Any],
        show_details: dict[str, Any],
        show_art: dict[str, str],
    ):
        self._show_id: int = show_details.get("id", -1)
        self._season: dict[str, Any] = season_details
        self._show_title: str = show_details.get("show_title", "TV Show")
        self._show_art: dict[str, str] = show_art
        self._season_number: int = self._season.get("season_number", -1)
        self._build()

    @property
    def isPlayable(self) -> bool:
        return False

    @property
    def url(self) -> str:
        return url(
            "/show/:show_id/season/:season_number/episodes/",
            show_id=self._show_id,
            season_number=self._season_number,
        )

    @property
    def label(self) -> str:
        season_num = self._season.get("season_number", 0)
        episode_count = self._season.get("episode_count", 0)
        name = self._season.get("name") or f"Season {season_num}"
        return f"{name}  ({episode_count} episodes)"

    def _apply_info(self, tag: xbmc.InfoTagVideo) -> None:
        s = self._season
        tag.setMediaType("season")
        tag.setTitle(self.label)
        tag.setPlot(s.get("overview") or "")
        tag.setSeason(s.get("season_number", 0))
        tag.setTvShowTitle(self._show_title)
        tag.setFirstAired(s.get("air_date") or "")

    def _apply_art(self, li: xbmcgui.ListItem) -> None:
        poster_path = self._season.get("poster_path") or ""
        season_poster = Tmdb.get_image_url(poster_path, "w500") if poster_path else ""
        art = self._show_art
        li.setArt(
            {
                "thumb": season_poster or art.get("poster", ""),
                "poster": season_poster or art.get("poster", ""),
                "fanart": art.get("fanart", ""),
                "clearlogo": art.get("clearlogo", ""),
                "landscape": art.get("landscape", ""),
            }
        )

    def _addContextMenuItems(self, li: xbmcgui.ListItem) -> None:
        pass
