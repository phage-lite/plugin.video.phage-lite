from typing import Any
import xbmc
import xbmcgui

from utils.router import url

from menu_items.menu_item import MenuItem

class MovieItem(MenuItem):
    def __init__(self, details: dict[str, Any], genre_str: str = ""):
        self._id: int = int(details.get("id") or 0)
        self.title: str = details.get("title", "Movie")
        self.year_str: str = details.get("release_date", "")[:4]
        self.poster_path: str = details.get("poster_path", "")
        self._details: dict[str, Any] = details
        self._genre_str: str = genre_str
        self._art: dict[str, str] = self.extract_art(details)
        self._build()

    @property
    def url(self) -> str:
        return url(
            "/play/",
            type="movie",
            id=self._id,
        )

    @property
    def isPlayable(self) -> bool:
        return True

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
        rem = url("/trakt/watchlist/remove/", type="movie", id=self._id)
        mw = url(
            "/trakt/watched/",
            type="movies",
            id=self._id,
        )
        ss = url(
            "/play/select/",
            type="movie",
            id=self._id,
        )
        li.addContextMenuItems(
            [
                ("Add to Favourites", f"RunPlugin({fav})"),
                ("Add to Watchlist", f"RunPlugin({wl})"),
                ("Remove From Watchlist", f"RunPlugin({rem})"),
                ("Mark as Watched", f"RunPlugin({mw})"),
                ("Select Source", f"PlayMedia({ss})"),
            ]
        )

    def _apply_info(self, tag: xbmc.InfoTagVideo) -> None:
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


