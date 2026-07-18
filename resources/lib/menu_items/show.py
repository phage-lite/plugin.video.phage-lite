from typing import Any
import xbmc
import xbmcgui

from utils.router import url

from menu_items.menu_item import MenuItem


class ShowItem(MenuItem):
    media_type: str = "show"

    def __init__(self, details: dict[str, Any], genre_str: str = ""):
        self._details: dict[str, Any] = details
        self._genre_str: str = genre_str
        self._art: dict[str, str] = self.extract_art(details)
        self._id: int = details.get("id", -1)
        self._year_str: str = details.get("first_air_date", "")[:4]
        self.poster_path: str = details.get("poster_path", "")
        self._build()

    @property
    def url(self) -> str:
        return url("/show/:show_id/seasons/", show_id=self._id)

    @property
    def label(self) -> str:
        return self._details.get("name", "TV Show")

    @property
    def isPlayable(self) -> bool:
        return False

    def _addContextMenuItems(self, li: xbmcgui.ListItem) -> None:
        fav = url(
            "/favourite/add/",
            type=self.media_type,
            id=self._id,
            title=self.label,
            year=self._year_str,
            poster=self.poster_path,
        )
        wl = url("/trakt/watchlist/add/", type=self.media_type, id=self._id)
        mw = url("/trakt/watched/", type=self.media_type, id=self._id)
        li.addContextMenuItems(
            [
                ("Add to Favourites", f"RunPlugin({fav})"),
                ("Add to Watchlist", f"RunPlugin({wl})"),
                ("Mark as Watched", f"RunPlugin({mw})"),
            ]
        )

    def _apply_info(self, tag: xbmc.InfoTagVideo) -> None:
        d = self._details
        title = d.get("name") or ""
        year_str = (d.get("first_air_date") or "")[:4]

        external_ids: dict[str, Any] = d.get("external_ids") or {}
        imdb_id = str(external_ids.get("imdb_id") or "")
        tvdb_id = str(external_ids.get("tvdb_id") or "")
        tmdb_id = str(d.get("id") or "")

        genres: list[str] = [g["name"] for g in (d.get("genres") or [])]
        credits: dict[str, Any] = d.get("credits") or {}

        tag.setMediaType("tvshow")
        tag.setTitle(title)
        tag.setOriginalTitle(d.get("original_name") or title)
        tag.setPlot(d.get("overview") or "")
        tag.setYear(int(year_str) if year_str.isdigit() else 0)
        tag.setRating(float(d.get("vote_average") or 0))
        tag.setVotes(int(d.get("vote_count") or 0))
        tag.setGenres(genres)
        tag.setIMDBNumber(imdb_id)
        tag.setUniqueIDs({"tmdb": tmdb_id, "imdb": imdb_id, "tvdb": tvdb_id})
        tag.setCast(self._build_cast(credits))

    def _apply_art(self, li: xbmcgui.ListItem) -> None:
        art = self._art
        li.setArt(
            {
                "thumb": art["poster"],
                "poster": art["poster"],
                "fanart": art["fanart"],
                "clearlogo": art["clearlogo"],
                "landscape": art["landscape"],
            }
        )
