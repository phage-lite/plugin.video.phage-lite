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
        self.session.headers.update(
            {
                "Accept": "application/json",
            }
        )

    def _get(self, endpoint: str, params: dict[str, Any] = {}) -> dict[str, Any]:
        url = f"{BASE_URL}/{endpoint}"
        headers = {
            "accept": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        response = self.session.get(url, params=params, headers=headers, timeout=20)
        response.raise_for_status()
        return response.json()

    def popular_movies(self, page: int = 1) -> dict[str, Any]:
        return self._get("movie/popular", {"page": page})

    def trending_movies(self, window: str = "week") -> dict[str, Any]:
        return self._get(f"trending/movie/{window}")

    def now_playing_movies(self, page: int = 1) -> dict[str, Any]:
        return self._get("movie/now_playing", {"page": page})

    def top_rated_movies(self, page: int = 1) -> dict[str, Any]:
        return self._get("movie/top_rated", {"page": page})

    def movie_genres(self) -> dict[str, Any]:
        return self._get("genre/movie/list")

    def movies_by_genre(self, genre_id: int, page: int = 1) -> dict[str, Any]:
        return self._get("discover/movie", {"with_genres": genre_id, "page": page})

    def popular_tv(self, page: int = 1) -> dict[str, Any]:
        return self._get("tv/popular", {"page": page})

    def trending_tv(self, window: str = "week") -> dict[str, Any]:
        return self._get(f"trending/tv/{window}")

    def airing_today_tv(self, page: int = 1) -> dict[str, Any]:
        return self._get("tv/airing_today", {"page": page})

    def top_rated_tv(self, page: int = 1) -> dict[str, Any]:
        return self._get("tv/top_rated", {"page": page})

    def tv_genres(self) -> dict[str, Any]:
        return self._get("genre/tv/list")

    def tv_by_genre(self, genre_id: int, page: int = 1) -> dict[str, Any]:
        return self._get("discover/tv", {"with_genres": genre_id, "page": page})


Tmdb = TmdbAPI()
