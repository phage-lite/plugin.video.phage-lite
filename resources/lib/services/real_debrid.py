from typing import override
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

    @override
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

    @override
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

    @override
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


RealDebrid = RealDebridAPI()
