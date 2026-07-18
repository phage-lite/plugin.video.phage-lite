import json
from typing import Any
import xbmc
import xbmcgui

from services.tmdb import Tmdb
from utils.router import url

from menu_items.menu_item import MenuItem


class EpisodeItem(MenuItem):
    def __init__(
        self,
        episode_number: int,
        season_details: dict[str, Any],
        show_details: dict[str, Any],
    ):
        self.episode_number: int = episode_number
        self._show_details: dict[str, Any] = show_details

        episodes: list[dict[str, Any]] = season_details.get("episodes", [])
        self.season_number: int = season_details.get("season_number", 0)
        self._episode_details: dict[str, Any] = next(
            (e for e in episodes if e["episode_number"] == episode_number)
        )
        self._id: int = self._episode_details.get("id", -1)
        self.show_title: str = show_details.get("name", "Unknown")
        self._show_id: int = show_details.get("id", -1)
        self._season_poster_path: str = season_details.get("poster_path", "")
        self._art: dict[str, Any] = self.extract_art(show_details)
        self._metadata: str = self._build_metadata()

        self._build()

    @property
    def label(self) -> str:
        ep_num = self._episode_details.get("episode_number", 0)
        ep_name = self._episode_details.get("name") or f"Episode {ep_num}"
        return f"{ep_num:02d} - {ep_name}"

    @property
    def url(self) -> str:
        return url(
            "/play/",
            type="episode",
            id=self._show_id,
            season=self.season_number,
            episode=self.episode_number,
            meta=self._metadata,
        )

    @property
    def isPlayable(self) -> bool:
        return True

    def _apply_info(self, tag: xbmc.InfoTagVideo) -> None:
        ep = self._episode_details
        ep_num = ep.get("episode_number", 0)
        ep_name = ep.get("name") or f"Episode {ep_num}"

        external_ids: dict[str, Any] = self._show_details.get("external_ids") or {}
        imdb_id = str(external_ids.get("imdb_id") or "")
        tvdb_id = str(external_ids.get("tvdb_id") or "")

        tag.setMediaType("episode")
        tag.setTitle(ep_name)
        tag.setOriginalTitle(ep_name)
        tag.setTvShowTitle(self.show_title)
        tag.setSeason(self.season_number)
        tag.setEpisode(ep_num)
        tag.setPlot(ep.get("overview") or "")
        tag.setDuration(int(ep.get("runtime") or 30) * 60)
        tag.setRating(float(ep.get("vote_average") or 0))
        tag.setFirstAired(ep.get("air_date") or "")
        tag.setIMDBNumber(imdb_id)
        tag.setUniqueIDs({"tmdb": str(self._show_id), "imdb": imdb_id, "tvdb": tvdb_id})
        tag.setCast(self._build_cast(self._show_details.get("credits") or {}))

    def _build_metadata(self) -> str:
        images = self._show_details.get("images", {})
        clearlogodata: dict[str, Any] = next(
            (i for i in images["logos"]),
            {"file_path": ""},
        )
        clearlogo = clearlogodata.get("file_path")

        return json.dumps(
            {
                "episodeid": self._id,
                "tvshowid": self._show_id,
                "title": self.label,
                "season": self.season_number,
                "episode": self.episode_number,
                "showtitle": self.show_title,
                "plot": str(self._episode_details.get("overview", "")),
                "playcount": int(self._episode_details.get("vote_count", 0)),
                "rating": int(self._episode_details.get("vote_average", 0)),
                "firstaired": str(self._episode_details.get("air_date", "1999-12-31")),
                "runtime": int(self._episode_details.get("runtime") or 30) * 60,
                "art": {
                    "thumb": Tmdb.get_image_url(
                        str(self._episode_details.get("still_path"))
                    ),
                    "tvshow.clearart": Tmdb.get_image_url(
                        str(self._show_details.get("backdrop_path")), "w1280"
                    ),
                    "tvshow.clearlogo": Tmdb.get_image_url(str(clearlogo)),
                    "tvshow.fanart": Tmdb.get_image_url(
                        str(self._show_details.get("backdrop_path")), "w1280"
                    ),
                    "tvshow.landscape": Tmdb.get_image_url(
                        str(self._episode_details.get("backdrop_path")), "w1280"
                    ),
                    "tvshow.poster": Tmdb.get_image_url(
                        str(self._show_details.get("poster_path")), "w780"
                    ),
                },
            }
        )

    def _apply_art(self, li: xbmcgui.ListItem) -> None:
        art = self._art
        still_url = Tmdb.get_image_url(self._episode_details.get("still_path", ""))
        season_url = Tmdb.get_image_url(self._season_poster_path, "w500")
        thumb = still_url or season_url or art["poster"]

        li.setArt(
            {
                "thumb": thumb,
                "poster": art["poster"],
                "fanart": art["fanart"],
                "clearlogo": art["clearlogo"],
                "landscape": art["landscape"],
                "tvshow.poster": art["poster"],
                "tvshow.fanart": art["fanart"],
                "tvshow.clearlogo": art["clearlogo"],
                "season.poster": season_url,
            }
        )

    def _addContextMenuItems(self, li: xbmcgui.ListItem) -> None:
        mw = url(
            "/trakt/watched/",
            type="episode",
            id=self._show_id,
            season=self.season_number,
            episode=self.episode_number,
        )
        ss = url(
            "/play/select/",
            type="episode",
            id=self._show_id,
            season=self.season_number,
            episode=self.episode_number,
            meta=self._metadata
        )
        li.addContextMenuItems(
            [
                ("Mark as Watched", f"RunPlugin({mw})"),
                ("Select Source", f"PlayMedia({ss})"),
            ]
        )


