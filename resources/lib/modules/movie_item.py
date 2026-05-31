from modules.playable_item import PlayableItem


class MovieItem(PlayableItem):
    def __init__(
        self,
        show_id: int,
        season_number: int,
        ep_num: int,
        label: str = "",
        label2: str = "",
        path: str = "",
        offscreen: bool = False,
    ) -> None:
        self.show_id: int = show_id
        self.season: int = season_number
        self.episode: int = ep_num
        super().__init__(label, label2, path, offscreen)
    def get_mark_watched_url(self) -> str:
        return super().get_mark_watched_url()

    def get_scrape_with_url(self, scraper: Scrapers) -> str:
        return super().get_scrape_with_url(scraper)

    def get_select_source_url(self) -> str:
        return super().get_select_source_url()

    def get_play_url(self) -> str:
        return url(
            "/play/",
            type="episode",
            id=self.show_id,
            season=self.season,
            episode=self.episode,
        )
