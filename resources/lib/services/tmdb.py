from typing import Any
from requests import Session
from settings.settings import get_setting
from settings.ids import SettingID as SID

BASE_URL = "https://api.themoviedb.org/3"
PREFIX = "tmdb"


class TmdbAPI:
    def __init__(self):
        self.api_key: str = get_setting(SID.CLIENT_SECRET, PREFIX)
        self.session: Session = Session()
        self.session.headers.update({"Accept": "application/json"})

    def _get(self, endpoint: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        url = f"{BASE_URL}/{endpoint}"
        headers = {
            "accept": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        lang = get_setting("language", PREFIX) or "en-US"
        merged: dict[str, Any] = {"language": lang}
        merged.update(params or {})
        response = self.session.get(url, params=merged, headers=headers, timeout=20)
        response.raise_for_status()
        return response.json()

    # ── Movies ───────────────────────────────────────────────────────────────

    def popular_movies(self, page: int = 1) -> dict[str, Any]:
        return self._get("movie/popular", {"page": page})

    def trending_movies(self, window: str = "week", page: int = 1) -> dict[str, Any]:
        return self._get(f"trending/movie/{window}", {"page": page})

    def now_playing_movies(self, page: int = 1) -> dict[str, Any]:
        return self._get("movie/now_playing", {"page": page})

    def upcoming_movies(self, page: int = 1) -> dict[str, Any]:
        return self._get("movie/upcoming", {"page": page})

    def top_rated_movies(self, page: int = 1) -> dict[str, Any]:
        return self._get("movie/top_rated", {"page": page})

    def movie_genres(self) -> dict[str, Any]:
        return self._get("genre/movie/list")

    def movies_by_genre(self, genre_id: int, page: int = 1) -> dict[str, Any]:
        return self._get("discover/movie", {"with_genres": genre_id, "page": page})

    def adult_movies(self, page: int = 1) -> dict[str, Any]:
        return self._get("discover/movie", {
            "include_adult": "true",
            "sort_by": "popularity.desc",
            "page": page,
        })

    # ── TV ───────────────────────────────────────────────────────────────────

    def popular_tv(self, page: int = 1) -> dict[str, Any]:
        return self._get("tv/popular", {"page": page})

    def trending_tv(self, window: str = "week", page: int = 1) -> dict[str, Any]:
        return self._get(f"trending/tv/{window}", {"page": page})

    def airing_today_tv(self, page: int = 1) -> dict[str, Any]:
        return self._get("tv/airing_today", {"page": page})

    def on_air_tv(self, page: int = 1) -> dict[str, Any]:
        return self._get("tv/on_the_air", {"page": page})

    def top_rated_tv(self, page: int = 1) -> dict[str, Any]:
        return self._get("tv/top_rated", {"page": page})

    def tv_genres(self) -> dict[str, Any]:
        return self._get("genre/tv/list")

    def tv_by_genre(self, genre_id: int, page: int = 1) -> dict[str, Any]:
        return self._get("discover/tv", {"with_genres": genre_id, "page": page})

    # ── Search ───────────────────────────────────────────────────────────────

    def search(self, query: str, page: int = 1) -> dict[str, Any]:
        return self._get("search/multi", {"query": query, "page": page, "include_adult": "false"})

    # ── Detail / metadata ────────────────────────────────────────────────────

    def movie_external_ids(self, tmdb_id: int) -> dict[str, Any]:
        return self._get(f"movie/{tmdb_id}/external_ids")

    def tv_external_ids(self, tmdb_id: int) -> dict[str, Any]:
        return self._get(f"tv/{tmdb_id}/external_ids")

    def movie_details(self, tmdb_id: int) -> dict[str, Any]:
        return self._get(f"movie/{tmdb_id}")

    def tv_details(self, tmdb_id: int) -> dict[str, Any]:
        return self._get(f"tv/{tmdb_id}")

    def tv_season(self, show_id: int, season_number: int) -> dict[str, Any]:
        return self._get(f"tv/{show_id}/season/{season_number}")

    def movie_rich_details(self, tmdb_id: int) -> dict[str, Any]:
        return self._get(f"movie/{tmdb_id}", {"append_to_response": "credits"})

    def tv_rich_details(self, tmdb_id: int) -> dict[str, Any]:
        return self._get(f"tv/{tmdb_id}", {"append_to_response": "credits"})


Tmdb = TmdbAPI()
