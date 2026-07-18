from abc import ABC, abstractmethod
from typing import Any
from typing_extensions import cast
import xbmc
import xbmcgui

from services.tmdb import Tmdb

class MenuItem(ABC):
    @property
    def label(self) -> str: ...

    @property
    def isPlayable(self) -> bool: ...

    @property
    def url(self) -> str: ...

    @property
    def listItem(self) -> xbmcgui.ListItem:
        return self._listItem

    def _build(self) -> None:
        self._listItem: xbmcgui.ListItem = xbmcgui.ListItem(
            label=self.label, label2=self.label
        )
        self._listItem.setProperty("IsPlayable", str(self.isPlayable))
        self._addContextMenuItems(self._listItem)

        tag = cast(xbmc.InfoTagVideo, self._listItem.getVideoInfoTag())
        self._apply_info(tag)
        self._apply_art(self._listItem)

    @abstractmethod
    def _apply_info(self, tag: xbmc.InfoTagVideo) -> None: ...

    @abstractmethod
    def _apply_art(self, li: xbmcgui.ListItem) -> None: ...

    @abstractmethod
    def _addContextMenuItems(self, li: xbmcgui.ListItem) -> None: ...

    @staticmethod
    def extract_art(details: dict[str, Any]) -> dict[str, str]:
        poster_path = details.get("poster_path", "")
        backdrop_path = details.get("backdrop_path", "")
        images: dict[str, Any] = details.get("images", {})

        poster = Tmdb.get_image_url(poster_path, "w780")
        fanart = Tmdb.get_image_url(backdrop_path, "w1280")
        clearlogo = ""
        landscape = ""

        logos: list[dict[str, Any]] = images.get("logos", [])
        backdrops: list[dict[str, Any]] = images.get("backdrops", [])
        posters: list[dict[str, Any]] = images.get("posters", [])

        for logo in logos:
            path = logo.get("file_path", "")
            if not path:
                continue
            if not path.lower().endswith(".png"):
                path = path.rsplit(".", 1)[0] + ".png"
            clearlogo = Tmdb.get_image_url(path, "original")
            break

        for bd in backdrops:
            if bd.get("iso_639_1") == "en":
                landscape = Tmdb.get_image_url(bd["file_path"], "w1280")
                break

        if not poster:
            for p in posters:
                if p.get("iso_639_1") == "en":
                    poster = Tmdb.get_image_url(p["file_path"], "w780")
                    break

        if not fanart:
            for bd in backdrops:
                if bd.get("iso_639_1") in (None, "xx", ""):
                    fanart = Tmdb.get_image_url(bd["file_path"], "w1280")
                    break

        return {
            "poster": poster,
            "fanart": fanart,
            "clearlogo": clearlogo,
            "landscape": landscape,
        }

    @staticmethod
    def _build_cast(credits: dict[str, Any], limit: int = 15) -> list[Any]:
        members: list[dict[str, Any]] = credits.get("cast") or []
        actors: list[xbmc.Actor] = []
        for i, m in enumerate(members[:limit]):
            thumb = (
                Tmdb.get_image_url(m["profile_path"], "h632")
                if m.get("profile_path")
                else ""
            )
            actors.append(
                xbmc.Actor(
                    name=m.get("name") or "",
                    role=m.get("character") or "",
                    order=i,
                    thumbnail=thumb,
                )
            )
        return actors


