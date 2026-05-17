from abc import ABC, abstractmethod
from enum import Enum
from typing import TypedDict


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
    @abstractmethod
    def start_auth(self) -> AuthData: ...
    @abstractmethod
    def poll(self) -> PollStatus: ...
    @abstractmethod
    def auth_complete(self) -> None: ...

# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────
#
#
# def _build_url(cfg: ServiceConfig, endpoint: str) -> str:
#     return f"{cfg.get('base_url')}/{endpoint}"
#
#
# def _build_headers(cfg: ServiceConfig, with_auth: bool = True):
#     headers = cfg.get("headers", lambda: {})()
#     if with_auth and cfg.get("auth_style") == "bearer":
#         token = get_setting(cfg["token_key"])
#         if token:
#             headers["Authorization"] = "Bearer " + token
#     return headers
#
#
# def _send(fn, *args, **kwargs):
#     resp = fn(*args, **kwargs)
#     if resp.status_code == 429:
#         retry_after = int(resp.headers.get("Retry-After", 1))
#         time.sleep(retry_after)
#         resp = fn(*args, **kwargs)
#     return resp
#
#
# def _parse(resp):
#     if "json" in resp.headers.get("Content-Type", ""):
#         return resp.json()
#     return resp.text
#
#
# # ─────────────────────────────────────────────────────────────────────────────
# # Public API
# # ─────────────────────────────────────────────────────────────────────────────
#
#
# def get(
#     service: str,
#     endpoint: str,
#     params: Any = None,
#     with_auth: bool = True,
#     timeout: int = 10,
#     raw: bool = False,
# ):
#     """
#     Pass raw=True to get the Response object directly (e.g. to read pagination headers).
#     """
#     cfg = services[service]
#     url = _build_url(cfg, endpoint)
#     headers = _build_headers(cfg, with_auth)
#     try:
#         resp = _send(requests.get, url, params=params, headers=headers, timeout=timeout)
#         if raw:
#             return resp
#         resp.raise_for_status()
#         return _parse(resp)
#     except Exception:
#         return None
#
#
# def post(
#     service: str,
#     endpoint: str,
#     data: Any = None,
#     params: Any = None,
#     with_auth: bool = True,
#     timeout: int = 10,
#     raw: bool = False,
#     form: bool = False,
# ):
#     cfg = services[service]
#     url = _build_url(cfg, endpoint)
#     headers = _build_headers(cfg, with_auth)
#     body_kwargs = {"data": data} if form else {"json": data}
#     try:
#         resp = _send(
#             requests.post,
#             url,
#             params=params,
#             headers=headers,
#             timeout=timeout,
#             **body_kwargs,
#         )
#         if raw:
#             return resp
#         resp.raise_for_status()
#         return _parse(resp)
#     except Exception:
#         return None
#
#
# def put(
#     service: str,
#     endpoint: str,
#     data: Any = None,
#     with_auth: bool = True,
#     timeout: int = 10,
# ):
#     cfg = services[service]
#     url = _build_url(cfg, endpoint)
#     headers = _build_headers(cfg, with_auth)
#     try:
#         resp = requests.put(url, json=data, headers=headers, timeout=timeout)
#         resp.raise_for_status()
#         return _parse(resp)
#     except Exception:
#         return None
#
#
# def delete(
#     service: str,
#     endpoint: str,
#     data: Any = None,
#     with_auth: bool = True,
#     timeout: int = 10,
#     raw: bool = False,
# ):
#     cfg = services[service]
#     url = _build_url(cfg, endpoint)
#     headers = _build_headers(cfg, with_auth)
#     try:
#         resp = requests.delete(url, json=data, headers=headers, timeout=timeout)
#         if raw:
#             return resp
#         resp.raise_for_status()
#         return _parse(resp)
#     except Exception:
#         return None
#
#
# # ─────────────────────────────────────────────────────────────────────────────
# # Auth helpers (read-only — write logic lives in the api files)
# # ─────────────────────────────────────────────────────────────────────────────
#
#
# def get_token(service: str):
#     return get_setting(services[service]["token_key"])
#
#
# def is_authorized(service: str):
#     return bool(get_token(service))
