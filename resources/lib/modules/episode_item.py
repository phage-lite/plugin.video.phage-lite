from typing_extensions import Any
from modules.playable_item import PlayableItem
from services.tmdb import Tmdb
from types.types import Scrapers
from utils.router import url


class EpisodeItem(PlayableItem):
    def __init__(self, ep_info: dict[str, Any], show_details: dict[str, Any]) -> None:
        self.show_id: int = int(show_details.get("show_id", -1))
        self.season: int = int(ep_info.get("season_number", -1))
        self.episode: int = int(ep_info.get("episode_number", -1))
        self.title: str = str(ep_info.get("name", f"Episode {self.episode}"))
        self.showtitle: str = str(show_details.get("title", ""))
        self.plot: str = str(ep_info.get("overview", ""))
        self.playcount: int = int(ep_info.get("vote_count", 0))
        self.rating: int = int(ep_info.get("vote_average", 0))
        self.firstaired: str = str(ep_info.get("air_date", "1999-12-31"))
        self.runtime: int = int(ep_info.get("runtime", 30))

        images = show_details.get("images", {})
        clearlogodata: dict[str, Any] = next(
            (i for i in images["logos"]),
            {"file_path": ""},
        )
        clearlogo = clearlogodata.get("file_path")
        self.listItem.setArt(
            {
                "thumb": Tmdb.get_image_url(str(ep_info.get("still_path")), "w500"),
                "poster": Tmdb.get_image_url(str(show_details.get("still_path"))),
                "banner": Tmdb.get_image_url(str(show_details.get("backdrop_path"))),
                "clearart": Tmdb.get_image_url(str(show_details.get("backdrop_path"))),
                "clearlogo": Tmdb.get_image_url(str(clearlogo)),
                "landscape": Tmdb.get_image_url(str(show_details.get("backdrop_path"))),
            }
        )

        label = f"{self.episode:02d}: {self.title}"
        super().__init__(label)

    def get_mark_watched_url(self) -> str:
        return url(
            "/trakt/watched/",
            type="episode",
            id=self.show_id,
            season=self.season,
            episode=self.episode,
        )

    def get_scrape_with_url(self, scraper: Scrapers) -> str:
        return url(
            "/play/select/",
            type="episode",
            id=self.show_id,
            season=self.season,
            episode=self.episode,
            scraper=str(scraper),
        )

    def get_select_source_url(self) -> str:
        return url(
            "/play/select/",
            type="episode",
            id=self.show_id,
            season=self.season,
            episode=self.episode,
        )

    def get_play_url(self) -> str:
        return url(
            "/play/",
            type="episode",
            id=self.show_id,
            season=self.season,
            episode=self.episode,
        )
