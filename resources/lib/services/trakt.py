import requests
from typing import Any

from typing_extensions import override

from utils.logger import log
from settings.settings import get_setting, set_setting
from services.types import AuthData, PollStatus, Service
from settings.ids import SettingID as SID

PREFIX = "trakt"
PAGE_SIZE = 20


class TraktAPI(Service):
    def __init__(self):
        self.client_id: str = get_setting(SID.CLIENT_ID, PREFIX)
        self.client_secret: str = get_setting(SID.CLIENT_SECRET, PREFIX)
        self.access_token: str = get_setting(SID.ACCESS_TOKEN, PREFIX)
        self.refresh_token: str = get_setting(SID.REFRESH_TOKEN, PREFIX)

        self.device_code: str = ""
        self.user_code: str = ""
        self.base_url: str = "https://api.trakt.tv"
        self.auth_url: str = f"{self.base_url}/oauth"
        self.token_url: str = f"{self.auth_url}/token"

    # ── OAuth device flow ─────────────────────────────────────────────────────

    @override
    def start_auth(self) -> AuthData:
        response = requests.post(
            f"{self.auth_url}/device/code",
            data={"client_id": self.client_id},
            timeout=20,
        )
        if not response.ok:
            raise Exception(response.json().get("error", "auth failed"))
        data = response.json()
        self.user_code = data["user_code"]
        self.device_code = data["device_code"]
        log(data)
        return {
            "verification_url": data["verification_url"],
            "direct_verification_url": f"{data['verification_url']}/{data['user_code']}",
            "user_code": self.user_code,
            "expiry": int(data["expires_in"]),
            "device_code": self.device_code,
            "interval": int(data["interval"]),
        }

    @override
    def poll(self) -> PollStatus:
        response = requests.post(
            f"{self.auth_url}/device/token",
            data={
                "code": self.device_code,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            },
            timeout=20,
        )
        match response.status_code:
            case 200:
                self.access_token = response.json()["access_token"]
                self.refresh_token = response.json()["refresh_token"]
                return PollStatus.SUCCESS
            case 410:
                return PollStatus.EXPIRED
            case 418:
                return PollStatus.DENIED
            case 404 | 409:
                return PollStatus.ERROR
            case _:
                return PollStatus.PENDING

    @override
    def auth_complete(self) -> None:
        if self.access_token:
            set_setting(SID.ACCESS_TOKEN, self.access_token, prefix=PREFIX)
            set_setting(SID.REFRESH_TOKEN, self.refresh_token, prefix=PREFIX)

    # ── Token management ──────────────────────────────────────────────────────

    def is_authenticated(self) -> bool:
        if not self.access_token:
            self.access_token = get_setting(SID.ACCESS_TOKEN, PREFIX)
        return bool(self.access_token)

    def _refresh_access_token(self) -> bool:
        if not self.refresh_token:
            self.refresh_token = get_setting(SID.REFRESH_TOKEN, PREFIX)
        if not self.refresh_token or not self.client_id or not self.client_secret:
            return False
        try:
            response = requests.post(
                self.token_url,
                json={
                    "refresh_token": self.refresh_token,
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "redirect_uri": "urn:ietf:wg:oauth:2.0:oob",
                    "grant_type": "refresh_token",
                },
                timeout=20,
            )
            response.raise_for_status()
            data = response.json()
            self.access_token = data["access_token"]
            self.refresh_token = data.get("refresh_token", self.refresh_token)
            set_setting(SID.ACCESS_TOKEN, self.access_token, prefix=PREFIX)
            set_setting(SID.REFRESH_TOKEN, self.refresh_token, prefix=PREFIX)
            return True
        except Exception as e:
            log(str(e), "_refresh_access_token")
            return False

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
            "trakt-api-version": "2",
            "trakt-api-key": self.client_id,
        }

    def _api_get(self, endpoint: str, params: dict[str, Any] | None = None) -> list[Any] | dict[str, Any]:
        url = f"{self.base_url}/{endpoint}"
        response = requests.get(url, headers=self._headers(), params=params or {}, timeout=20)
        if response.status_code == 401 and self._refresh_access_token():
            response = requests.get(url, headers=self._headers(), params=params or {}, timeout=20)
        response.raise_for_status()
        return response.json()

    def _api_post(self, endpoint: str, body: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.base_url}/{endpoint}"
        response = requests.post(url, headers=self._headers(), json=body, timeout=20)
        if response.status_code == 401 and self._refresh_access_token():
            response = requests.post(url, headers=self._headers(), json=body, timeout=20)
        if response.ok and response.content:
            return response.json()
        return {}

    # ── Scrobble ──────────────────────────────────────────────────────────────

    def scrobble(self, action: str, media_type: str, tmdb_id: int, progress: float,
                 season: int = 0, episode: int = 0) -> None:
        if not self.is_authenticated():
            return
        if media_type in ("episode", "tv", "show"):
            body: dict[str, Any] = {
                "show": {"ids": {"tmdb": tmdb_id}},
                "episode": {"season": season, "number": episode},
                "progress": round(progress, 1),
            }
        else:
            body = {"movie": {"ids": {"tmdb": tmdb_id}}, "progress": round(progress, 1)}
        try:
            _ = self._api_post(f"scrobble/{action}", body)
        except Exception as e:
            log(str(e), f"scrobble/{action}")

    # ── Watchlist sync ────────────────────────────────────────────────────────

    def add_to_watchlist(self, media_type: str, tmdb_id: int) -> None:
        key = "movies" if media_type == "movie" else "shows"
        _ = self._api_post("sync/watchlist", {key: [{"ids": {"tmdb": tmdb_id}}]})

    def remove_from_watchlist(self, media_type: str, tmdb_id: int) -> None:
        key = "movies" if media_type == "movie" else "shows"
        _ = self._api_post("sync/watchlist/remove", {key: [{"ids": {"tmdb": tmdb_id}}]})

    # ── Show progress (for Up Next) ───────────────────────────────────────────

    def show_progress(self, trakt_id: int) -> dict[str, Any]:
        result = self._api_get(
            f"shows/{trakt_id}/progress/watched",
            {"specials": "false", "count_specials": "false"},
        )
        return result if isinstance(result, dict) else {}

    def my_calendar(self, days: int = 7) -> dict[str, list[dict[str, Any]]]:
        from datetime import date
        start = date.today().isoformat()
        result = self._api_get(
            f"calendars/my/shows/{start}/{days}",
            {"extended": "full"},
        )
        return result if isinstance(result, dict) else {}

    def mark_watched_movie(self, tmdb_id: int) -> None:
        _ = self._api_post("sync/history", {"movies": [{"ids": {"tmdb": tmdb_id}}]})

    def mark_watched_episode(self, tmdb_id: int, season: int, episode: int) -> None:
        _ = self._api_post("sync/history", {
            "shows": [{
                "ids": {"tmdb": tmdb_id},
                "seasons": [{"number": season, "episodes": [{"number": episode}]}],
            }]
        })

    # ── Watchlist ─────────────────────────────────────────────────────────────

    def watched_shows(self, limit: int = 30) -> list[dict[str, Any]]:
        result = self._api_get(
            "users/me/watched/shows",
            {"extended": "noseasons"},
        )
        items = result if isinstance(result, list) else []
        return items[:limit]

    def watchlist_movies(self, page: int = 1, limit: int = PAGE_SIZE) -> list[dict[str, Any]]:
        result = self._api_get(
            "users/me/watchlist/movies",
            {"extended": "full", "limit": limit, "page": page},
        )
        return result if isinstance(result, list) else []

    def watchlist_shows(self, page: int = 1, limit: int = PAGE_SIZE) -> list[dict[str, Any]]:
        result = self._api_get(
            "users/me/watchlist/shows",
            {"extended": "full", "limit": limit, "page": page},
        )
        return result if isinstance(result, list) else []

    # ── Recommendations ───────────────────────────────────────────────────────

    def recommendations_movies(self, page: int = 1, limit: int = PAGE_SIZE) -> list[dict[str, Any]]:
        result = self._api_get(
            "recommendations/movies",
            {"extended": "full", "limit": limit, "page": page},
        )
        return result if isinstance(result, list) else []

    def recommendations_shows(self, page: int = 1, limit: int = PAGE_SIZE) -> list[dict[str, Any]]:
        result = self._api_get(
            "recommendations/shows",
            {"extended": "full", "limit": limit, "page": page},
        )
        return result if isinstance(result, list) else []


Trakt = TraktAPI()
