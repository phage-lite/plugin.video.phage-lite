import json
from datetime import date, timedelta
from typing import Any
from requests import Session
from settings.settings import get_setting
from settings.ids import SettingID as SID
from utils import cache as _cache
from utils.logger import log

BASE_URL = "https://api.themoviedb.org/3"
PREFIX = "tmdb"


class TmdbAPI:
    def __init__(self):
        self.api_key: str = get_setting(SID.CLIENT_SECRET, PREFIX)
        self.session: Session = Session()
        self.session.headers.update({"Accept": "application/json"})

    def _get(
        self, endpoint: str, params: dict[str, Any] | None = None, ttl: int = 0
    ) -> dict[str, Any]:
        url = f"{BASE_URL}/{endpoint}"
        headers = {
            "accept": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        _, region = self._lang_parts()
        lang = get_setting("language", PREFIX) or "en-US"
        merged: dict[str, Any] = {"language": lang, "include_adult": "false"}
        if region:
            merged["region"] = region
        merged.update(params or {})

        key = endpoint + json.dumps(sorted(merged.items())) if ttl > 0 else ""
        if ttl > 0:
            hit: dict[str, Any] | None = _cache.get(key, ttl)
            if hit is not None:
                return hit

        response = self.session.get(url, params=merged, headers=headers, timeout=20)
        response.raise_for_status()
        result: dict[str, Any] = response.json()

        if ttl > 0:
            _cache.set(key, result)

        return result

    def _lang_parts(self) -> tuple[str, str]:
        """Return (lang_code, region_code) from the language setting, e.g. 'en-US' → ('en', 'US')."""
        raw = get_setting("language", PREFIX) or "en-US"
        parts = raw.split("-", 1)
        lang = parts[0].lower()
        region = parts[1].upper() if len(parts) > 1 else ""
        return lang, region

    def _date(self, offset_days: int = 0) -> str:
        return (date.today() + timedelta(days=offset_days)).strftime("%Y-%m-%d")

    def _sort_param(self, media: str) -> str:
        idx = get_setting("list_sort", "tmdblist")
        match idx:
            case "1":
                return "vote_average.desc"
            case "2":
                return (
                    "primary_release_date.desc"
                    if media == "movie"
                    else "first_air_date.desc"
                )
            case "3":
                return "original_title.asc"
            case _:
                return "popularity.desc"

    # ── Movies ───────────────────────────────────────────────────────────────

    def popular_movies(self, page: int = 1) -> dict[str, Any]:
        lang, _ = self._lang_parts()
        return self._get(
            "discover/movie",
            {
                "sort_by": "popularity.desc",
                "with_original_language": lang,
                "vote_count.gte": 10,
                "page": page,
            },
            ttl=1800,
        )

    def trending_movies(self, window: str = "week", page: int = 1) -> dict[str, Any]:
        # /trending has no discover equivalent — inherently global
        return self._get(f"trending/movie/{window}", {"page": page}, ttl=1800)

    def now_playing_movies(self, page: int = 1) -> dict[str, Any]:
        lang, _ = self._lang_parts()
        return self._get(
            "discover/movie",
            {
                "sort_by": "popularity.desc",
                "with_release_type": "2|3",
                "release_date.gte": self._date(-45),
                "release_date.lte": self._date(),
                "with_original_language": lang,
                "page": page,
            },
            ttl=1800,
        )

    def upcoming_movies(self, page: int = 1) -> dict[str, Any]:
        lang, _ = self._lang_parts()
        return self._get(
            "discover/movie",
            {
                "sort_by": "release_date.asc",
                "release_date.gte": self._date(1),
                "release_date.lte": self._date(90),
                "with_original_language": lang,
                "page": page,
            },
            ttl=1800,
        )

    def top_rated_movies(self, page: int = 1) -> dict[str, Any]:
        lang, _ = self._lang_parts()
        return self._get(
            "discover/movie",
            {
                "sort_by": "vote_average.desc",
                "vote_count.gte": 300,
                "with_original_language": lang,
                "page": page,
            },
            ttl=1800,
        )

    def movie_genres(self) -> dict[str, Any]:
        return self._get("genre/movie/list", ttl=86400)

    def movies_by_genre(self, genre_id: int, page: int = 1) -> dict[str, Any]:
        lang_code, _ = self._lang_parts()
        return self._get(
            "discover/movie",
            {
                "with_genres": genre_id,
                "page": page,
                "sort_by": self._sort_param("movie"),
                "with_original_language": lang_code,
            },
            ttl=1800,
        )

    # ── TV ───────────────────────────────────────────────────────────────────

    def popular_tv(self, page: int = 1) -> dict[str, Any]:
        lang, _ = self._lang_parts()
        return self._get(
            "discover/tv",
            {
                "sort_by": "popularity.desc",
                "with_original_language": lang,
                "page": page,
            },
            ttl=1800,
        )

    def trending_tv(self, window: str = "week", page: int = 1) -> dict[str, Any]:
        # /trending has no discover equivalent — inherently global
        return self._get(f"trending/tv/{window}", {"page": page}, ttl=1800)

    def airing_today_tv(self, page: int = 1) -> dict[str, Any]:
        lang, _ = self._lang_parts()
        today = self._date()
        return self._get(
            "discover/tv",
            {
                "sort_by": "popularity.desc",
                "air_date.gte": today,
                "air_date.lte": today,
                "with_original_language": lang,
                "page": page,
            },
            ttl=1800,
        )

    def on_air_tv(self, page: int = 1) -> dict[str, Any]:
        lang, _ = self._lang_parts()
        return self._get(
            "discover/tv",
            {
                "sort_by": "popularity.desc",
                "air_date.gte": self._date(),
                "air_date.lte": self._date(7),
                "with_original_language": lang,
                "page": page,
            },
            ttl=1800,
        )

    def top_rated_tv(self, page: int = 1) -> dict[str, Any]:
        lang, _ = self._lang_parts()
        return self._get(
            "discover/tv",
            {
                "sort_by": "vote_average.desc",
                "vote_count.gte": 50,
                "with_original_language": lang,
                "page": page,
            },
            ttl=1800,
        )

    def tv_genres(self) -> dict[str, Any]:
        return self._get("genre/tv/list", ttl=86400)

    def tv_by_genre(self, genre_id: int, page: int = 1) -> dict[str, Any]:
        lang_code, _ = self._lang_parts()
        return self._get(
            "discover/tv",
            {
                "with_genres": genre_id,
                "page": page,
                "sort_by": self._sort_param("tv"),
                "with_original_language": lang_code,
            },
            ttl=1800,
        )

    # ── Similar / Recommended ────────────────────────────────────────────────

    def similar_movies(self, tmdb_id: int, page: int = 1) -> dict[str, Any]:
        return self._get(f"movie/{tmdb_id}/similar", {"page": page}, ttl=900)

    def recommended_movies(self, tmdb_id: int, page: int = 1) -> dict[str, Any]:
        return self._get(f"movie/{tmdb_id}/recommendations", {"page": page}, ttl=900)

    def similar_tv(self, tmdb_id: int, page: int = 1) -> dict[str, Any]:
        return self._get(f"tv/{tmdb_id}/similar", {"page": page}, ttl=900)

    def recommended_tv(self, tmdb_id: int, page: int = 1) -> dict[str, Any]:
        return self._get(f"tv/{tmdb_id}/recommendations", {"page": page}, ttl=900)

    # ── Search ───────────────────────────────────────────────────────────────

    def search(self, query: str, page: int = 1) -> dict[str, Any]:
        return self._get(
            "search/multi", {"query": query, "page": page, "include_adult": "false"}
        )

    # ── Detail / metadata ────────────────────────────────────────────────────

    def movie_external_ids(self, tmdb_id: int) -> dict[str, Any]:
        return self._get(f"movie/{tmdb_id}/external_ids", ttl=7200)

    def tv_external_ids(self, tmdb_id: int) -> dict[str, Any]:
        return self._get(f"tv/{tmdb_id}/external_ids", ttl=7200)

    def movie_details(self, tmdb_id: int) -> dict[str, Any]:
        return self._get(f"movie/{tmdb_id}", ttl=7200)

    def tv_details(self, tmdb_id: int) -> dict[str, Any]:
        return self._get(f"tv/{tmdb_id}", ttl=7200)

    def tv_season(self, show_id: int, season_number: int) -> dict[str, Any]:
        return self._get(f"tv/{show_id}/season/{season_number}", ttl=7200)

    def movie_rich_details(self, tmdb_id: int) -> dict[str, Any]:
        return self._get(
            f"movie/{tmdb_id}", {"append_to_response": "credits"}, ttl=7200
        )

    def tv_rich_details(self, tmdb_id: int) -> dict[str, Any]:
        return self._get(f"tv/{tmdb_id}", {"append_to_response": "credits"}, ttl=7200)


Tmdb = TmdbAPI()
