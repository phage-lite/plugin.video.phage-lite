from typing import Any
import requests
from services.types import Service, AuthData, PollStatus
from utils.logger import log
from settings.ids import SettingID as SID
from settings.settings import get_setting, set_setting


# "real_debrid": {
#     "base_url": "https://api.real-debrid.com",
#     "auth_endpoint": "/oauth/v2/auth/device/code?client_id=%s&new_credentials=yes",
#     # ?client_id=ABCDEFGHIJKLM&redirect_uri=https%3A%2F%2Fexample.com&response_type=code&state=iloverd
#     "auth_style": "bearer",
#     "token_key": "rd.token",
# },
# {
#         "base_url": "https://api.trakt.tv",
#         "auth_style": "bearer",
#         "token_key": "trakt.token",
#         "headers": lambda: {
#             "Content-Type": "application/json",
#             "trakt-api-version": "2",
#             "trakt-api-key": get_setting("trakt.client"),
#         },
#     }
RD_PREFIX = "rd"


class RealDebridAPI(Service):
    def __init__(self):
        self.app_id: str = get_setting(SID.APP_ID, RD_PREFIX)
        self.client_id: str = get_setting(SID.CLIENT_ID, RD_PREFIX)
        self.client_secret: str = get_setting(SID.CLIENT_SECRET, RD_PREFIX)
        self.access_token: str = get_setting(SID.ACCESS_TOKEN, RD_PREFIX)
        self.refresh_token: str = get_setting(SID.REFRESH_TOKEN, RD_PREFIX)

        self.device_code: str = ""
        self.user_code: str = ""
        self.auth_url: str = "https://api.real-debrid.com/oauth/v2"
        self.token_url: str = f"{self.auth_url}/token"
        self.refresh_retries: int = 0
        self.break_auth_loop: bool = False

    def start_auth(self) -> AuthData:
        device_code_url: str = (
            f"{self.auth_url}/device/code?client_id={self.app_id}&new_credentials=yes"
        )
        response = requests.get(device_code_url, timeout=20).json()

        if "error" in response:
            raise Exception(response["error"])

        self.user_code = response["user_code"]
        self.device_code = response["device_code"]
        log(response)

        return {
            "verification_url": response["verification_url"],
            "direct_verification_url": response["direct_verification_url"],
            "user_code": self.user_code,
            "expiry": int(response["expires_in"]),
            "device_code": self.device_code,
            "interval": int(response["interval"]),
        }

    def poll(self) -> PollStatus:
        poll_status = PollStatus.PENDING
        poll_url: str = f"{self.auth_url}/device/credentials?client_id={self.app_id}&code={self.device_code}"
        response = requests.get(poll_url, timeout=20).json()
        log(poll_url, "poll")
        log(response, "poll")
        if "error" in response:
            poll_status = PollStatus.PENDING
        else:
            self.client_id = response["client_id"]
            self.client_secret = response["client_secret"]
            log(self.client_id)
            log(self.client_secret)
            poll_status = PollStatus.SUCCESS
        return poll_status

    def auth_complete(self) -> None:
        if self.client_secret:
            data = {
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "code": self.device_code,
                "grant_type": "http://oauth.net/grant_type/device/1.0",
            }
            try:
                response = requests.post(self.token_url, data=data, timeout=20).json()
                log(response)
                self.access_token = response["access_token"]
                self.refresh_token = response["refresh_token"]
                set_setting(SID.ACCESS_TOKEN, self.access_token, RD_PREFIX)
                set_setting(SID.REFRESH_TOKEN, self.refresh_token, RD_PREFIX)
                set_setting(SID.CLIENT_SECRET, self.client_secret, RD_PREFIX)
                set_setting(SID.CLIENT_ID, self.client_id, RD_PREFIX)
            except Exception as e:
                log(str(e))

    def _refresh_token(self) -> bool:
        if not self.refresh_token or not self.client_id or not self.client_secret:
            return False
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": self.refresh_token,
            "grant_type": "http://oauth.net/grant_type/device/1.0",
        }
        try:
            response = requests.post(self.token_url, data=data, timeout=20)
            response.raise_for_status()
            result: dict[str, Any] = response.json()
            self.access_token = result["access_token"]
            self.refresh_token = result.get("refresh_token", self.refresh_token)
            set_setting(SID.ACCESS_TOKEN, self.access_token, RD_PREFIX)
            set_setting(SID.REFRESH_TOKEN, self.refresh_token, RD_PREFIX)
            return True
        except Exception as e:
            log(str(e), "_refresh_token")
            return False

    def _api_get(self, endpoint: str, params: dict[str, str] | None = None) -> dict[str, Any]:
        url = f"https://api.real-debrid.com/rest/1.0/{endpoint}"
        headers = {"Authorization": f"Bearer {self.access_token}"}
        response = requests.get(url, headers=headers, params=params or {}, timeout=20)
        if response.status_code in (401, 403) and self._refresh_token():
            headers["Authorization"] = f"Bearer {self.access_token}"
            response = requests.get(url, headers=headers, params=params or {}, timeout=20)
        response.raise_for_status()
        return response.json()

    def _api_post(self, endpoint: str, data: dict[str, str] | None = None) -> dict[str, Any]:
        url = f"https://api.real-debrid.com/rest/1.0/{endpoint}"
        headers = {"Authorization": f"Bearer {self.access_token}"}
        response = requests.post(url, headers=headers, data=data or {}, timeout=20)
        if response.status_code in (401, 403) and self._refresh_token():
            headers["Authorization"] = f"Bearer {self.access_token}"
            response = requests.post(url, headers=headers, data=data or {}, timeout=20)
        response.raise_for_status()
        if not response.content:
            return {}
        return response.json()

    def unrestrict_link(self, link: str) -> dict[str, Any]:
        return self._api_post("unrestrict/link", {"link": link})

    def add_magnet(self, magnet: str) -> dict[str, Any]:
        return self._api_post("torrents/addMagnet", {"magnet": magnet})

    def get_torrent_info(self, torrent_id: str) -> dict[str, Any]:
        return self._api_get(f"torrents/info/{torrent_id}")

    def select_files(self, torrent_id: str, file_ids: str = "all") -> None:
        _ = self._api_post(f"torrents/selectFiles/{torrent_id}", {"files": file_ids})

    def get_downloads(self) -> list[dict[str, Any]]:
        result = self._api_get("downloads")
        return result if isinstance(result, list) else []

    def is_authenticated(self) -> bool:
        return bool(self.access_token)

    def check_instant_availability(self, hashes: list[str]) -> set[str]:
        if not hashes or not self.access_token:
            return set()
        cached: set[str] = set()
        for i in range(0, len(hashes), 40):
            chunk = hashes[i:i + 40]
            endpoint = "torrents/instantAvailability/" + "/".join(chunk)
            try:
                result = self._api_get(endpoint)
                for h, data in result.items():
                    if isinstance(data, dict) and data.get("rd"):
                        cached.add(h.lower())
            except Exception as e:
                log(str(e), "check_instant_availability")
        return cached


RealDebrid = RealDebridAPI()
