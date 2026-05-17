import requests

from utils.logger import log
from settings.settings import get_setting, set_setting
from services.types import AuthData, PollStatus, Service
from settings.ids import SettingID as SID

PREFIX = "tmdb"

class TmdbAPI(Service):
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
        self.refresh_retries: int = 0
        self.break_auth_loop: bool = False

    @override
    def start_auth(self) -> AuthData:
        device_code_url: str = f"{self.auth_url}/device/code"
        data = {"client_id": self.client_id}
        response = requests.post(device_code_url, data=data, timeout=20)

        if not response.ok:
            log(str(response))
            raise Exception(response.json()["error"])

        self.user_code = response.json()["user_code"]
        self.device_code = response.json()["device_code"]
        direct_verification_url = (
            f"{response.json()['verification_url']}/{response.json()['user_code']}"
        )
        log(response.json())

        return {
            "verification_url": response.json()["verification_url"],
            "direct_verification_url": direct_verification_url,
            "user_code": self.user_code,
            "expiry": int(response.json()["expires_in"]),
            "device_code": self.device_code,
            "interval": int(response.json()["interval"]),
        }

    @override
    def poll(self) -> PollStatus:
        poll_status = PollStatus.PENDING
        poll_url: str = f"{self.auth_url}/device/token"
        data = {
            "code": self.device_code,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }
        response = requests.post(poll_url, data=data, timeout=20)

        match response.status_code:
            case 400:
                poll_status = PollStatus.PENDING
            case 200:
                self.access_token = response.json()["access_token"]
                self.refresh_token = response.json()["refresh_token"]
                poll_status = PollStatus.SUCCESS
            case 404:
                poll_status = PollStatus.ERROR
            case 409:
                poll_status = PollStatus.ERROR
            case 410:
                poll_status = PollStatus.EXPIRED
            case 418:
                poll_status = PollStatus.DENIED
            case _:
                poll_status = PollStatus.PENDING

        return poll_status

    @override
    def auth_complete(self) -> None:
        if self.access_token:
            set_setting(SID.ACCESS_TOKEN, self.access_token, prefix=PREFIX)
            set_setting(SID.REFRESH_TOKEN, self.refresh_token, prefix=PREFIX)


Tmdb = TmdbAPI()
