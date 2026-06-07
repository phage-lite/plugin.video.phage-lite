from typing import Any
from typing_extensions import cast
import xbmc
import xbmcgui

from services.tmdb import Tmdb
from utils.router import url


class ListItemBase:
    is_folder: bool = False

    @property
    def label(self) -> str:
        raise NotImplementedError

    def build(self) -> xbmcgui.ListItem:
        li = xbmcgui.ListItem(label=self.label, label2=self.label)
        if not self.is_folder:
            li.setProperty("IsPlayable", "true")
            self._addContextMenuItems(li)

        tag = cast(xbmc.InfoTagVideo, li.getVideoInfoTag())
        self._apply_info(li, tag)
        self._apply_art(li)
        return li

    def _apply_info(self, li: xbmcgui.ListItem, tag: Any) -> None:
        pass

    def _apply_art(self, li: xbmcgui.ListItem) -> None:
        pass

    def _addContextMenuItems(self, li: xbmcgui.ListItem) -> None:
        pass

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


class EpisodeItem(ListItemBase):
    is_folder: bool = False

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
        self.show_title: str = show_details.get("name", "Unknown")
        self._show_id: int = show_details.get("id", -1)
        self._season_poster_path: str = season_details.get("poster_path", "")
        self.play_url: str = url(
            "/play/",
            type="episode",
            id=self._show_id,
            season=self.season_number,
            episode=self.episode_number,
        )
        self._art: dict[str, Any] = self.extract_art(show_details)

    @property
    def label(self) -> str:
        ep_num = self._episode_details.get("episode_number", 0)
        ep_name = self._episode_details.get("name") or f"Episode {ep_num}"
        return f"{ep_num:02d} - {ep_name}"

    def _apply_info(self, li: xbmcgui.ListItem, tag: xbmc.InfoTagVideo) -> None:
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
        )
        sw_torrentio = url(
            "/play/select/",
            type="episode",
            id=self._show_id,
            season=self.season_number,
            episode=self.episode_number,
            scraper="torrentio",
        )
        sw_cocos = url(
            "/play/select/",
            type="episode",
            id=self._show_id,
            season=self.season_number,
            episode=self.episode_number,
            scraper="cocoscrapers",
        )
        li.addContextMenuItems(
            [
                ("Mark as Watched", f"RunPlugin({mw})"),
                ("Select Source", f"PlayMedia({ss})"),
                ("Scrape with Torrentio", f"PlayMedia({sw_torrentio})"),
                ("Scrape with CocoScrapers", f"PlayMedia({sw_cocos})"),
            ]
        )


class MovieItem(ListItemBase):
    is_folder: bool = False

    def __init__(self, details: dict[str, Any], genre_str: str = ""):
        self._id = int(details.get("id") or 0)
        self.title = details.get("title", "Movie")
        self.year_str = details.get("release_date", "")[:4]
        self.poster_path = details.get("poster_path", "")
        self._details: dict[str, Any] = details
        self._genre_str: str = genre_str
        self._art: dict[str, str] = self.extract_art(details)
        self.play_url: str = url(
            "/play/",
            type="movie",
            id=self._id,
        )

    @property
    def label(self) -> str:
        return self._details.get("title") or "Unknown"

    def _addContextMenuItems(self, li: xbmcgui.ListItem) -> None:
        fav = url(
            "/favourite/add/",
            type="movie",
            id=self._id,
            title=self.title,
            year=self.year_str,
            poster=self.poster_path,
        )
        wl = url("/trakt/watchlist/add/", type="movie", id=self._id)
        mw = url(
            "/trakt/watched/",
            type="movies",
            id=self._id,
        )
        ss = url(
            "/play/select/",
            type="menus",
            id=self._id,
        )
        sw_torrentio = url(
            "/play/select/",
            type="menus",
            id=self._id,
            scraper="torrentio",
        )
        sw_cocos = url(
            "/play/select/",
            type="menus",
            id=self._id,
            scraper="cocoscrapers",
        )
        li.addContextMenuItems(
            [
                ("Add to Favourites", f"RunPlugin({fav})"),
                ("Add to Watchlist", f"RunPlugin({wl})"),
                ("Mark as Watched", f"RunPlugin({mw})"),
                ("Select Source", f"PlayMedia({ss})"),
                ("Scrape with Torrentio", f"PlayMedia({sw_torrentio})"),
                ("Scrape with CocoScrapers", f"PlayMedia({sw_cocos})"),
            ]
        )

    def _apply_info(self, li: xbmcgui.ListItem, tag: Any) -> None:
        d = self._details
        title = d.get("title", "Movie")
        year_str: str = d.get("release_date", "")[:4]

        external_ids: dict[str, Any] = d.get("external_ids") or {}
        imdb_id = str(external_ids.get("imdb_id") or d.get("imdb_id") or "")
        tmdb_id = str(d.get("id") or "")

        credits: dict[str, Any] = d.get("credits") or {}
        crew: list[dict[str, Any]] = credits.get("crew") or []
        directors = [c["name"] for c in crew if c.get("job") == "Director"]
        writers = [
            c["name"]
            for c in crew
            if c.get("job") in ("Writer", "Screenplay", "Author", "Characters")
        ]
        studios = [
            c["name"] for c in (d.get("production_companies") or []) if c.get("name")
        ][:3]

        genres = [g["name"] for g in (d.get("genres") or [])]

        mpaa = ""
        for entry in (d.get("release_dates") or {}).get("results") or []:
            if entry.get("iso_3166_1") == "US":
                for rd in entry.get("release_dates") or []:
                    cert = rd.get("certification") or ""
                    if cert:
                        mpaa = cert
                        break
                if mpaa:
                    break

        trailer = ""
        for v in (d.get("videos") or {}).get("results") or []:
            if v.get("site") == "YouTube" and v.get("type") == "Trailer":
                trailer = f"plugin://plugin.video.youtube/play/?video_id={v['key']}"
                break

        tag.setMediaType("movie")
        tag.setTitle(title)
        tag.setOriginalTitle(d.get("original_title") or title)
        tag.setPlot(d.get("overview") or "")
        tag.setTagLine(d.get("tagline") or "")
        tag.setYear(int(year_str) if year_str.isdigit() else 0)
        tag.setRating(float(d.get("vote_average") or 0))
        tag.setVotes(int(d.get("vote_count") or 0))
        tag.setGenres(genres)
        tag.setStudios(studios)
        tag.setMpaa(mpaa)
        tag.setDirectors(directors)
        tag.setWriters(writers)
        tag.setIMDBNumber(imdb_id)
        tag.setTrailer(trailer)
        tag.setUniqueIDs({"tmdb": tmdb_id, "imdb": imdb_id})
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


class ShowItem(ListItemBase):
    is_folder: bool = True

    def __init__(self, details: dict[str, Any], genre_str: str = ""):
        self._details: dict[str, Any] = details
        self._genre_str: str = genre_str
        self._art: dict[str, str] = self.extract_art(details)

    @property
    def label(self) -> str:
        return self._details.get("name") or "Unknown"

    def _apply_info(self, li: xbmcgui.ListItem, tag: Any) -> None:
        d = self._details
        title = d.get("name") or ""
        year_str = (d.get("first_air_date") or "")[:4]

        external_ids: dict[str, Any] = d.get("external_ids") or {}
        imdb_id = str(external_ids.get("imdb_id") or "")
        tvdb_id = str(external_ids.get("tvdb_id") or "")
        tmdb_id = str(d.get("id") or "")

        genres = [g["name"] for g in (d.get("genres") or [])]
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


class SeasonItem(ListItemBase):
    is_folder: bool = True

    def __init__(
        self, season: dict[str, Any], show_title: str, show_art: dict[str, str]
    ):
        self._season: dict[str, Any] = season
        self._show_title: str = show_title
        self._show_art: dict[str, str] = show_art

    @property
    def label(self) -> str:
        season_num = self._season.get("season_number", 0)
        episode_count = self._season.get("episode_count", 0)
        name = self._season.get("name") or f"Season {season_num}"
        return f"{name}  ({episode_count} episodes)"

    def _apply_info(self, li: xbmcgui.ListItem, tag: Any) -> None:
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
