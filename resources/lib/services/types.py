from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, TypedDict

from settings.settings import get_setting, set_setting
from utils.logger import log


class AuthData(TypedDict):
    user_code: str
    verification_url: str
    direct_verification_url: str
    device_code: str
    expiry: int
    interval: int


class PollStatus(Enum):
    PENDING = ("pending",)
    SUCCESS = ("success",)
    EXPIRED = ("expired",)
    DENIED = ("denied",)
    ERROR = "error"


class Service(ABC):
    @property
    @abstractmethod
    def setting_prefix(self) -> str: ...
    @abstractmethod
    def start_auth(self) -> AuthData: ...
    @abstractmethod
    def poll(self) -> PollStatus: ...
    @abstractmethod
    def auth_complete(self) -> None: ...
    @property
    @abstractmethod
    def is_authenticated(self) -> bool: ...
    @property
    @abstractmethod
    def _headers(self) -> dict[str, str]: ...

    def _get_setting(self, setting_id: str) -> Any:
        return get_setting(setting_id, prefix=self.setting_prefix)

    def _set_setting(self, setting_id: str, value: str) -> None:
        set_setting(setting_id, value, prefix=self.setting_prefix)

    @property
    def is_enabled(self) -> bool:
        return self._get_setting("enabled") == "true"
