import requests
from typing import Any

from settings.settings import get_setting
from utils.logger import log

PREFIX = "torbox"
BASE_URL = "https://api.torbox.app/v1/api"

_VIDEO_EXTS = {".mkv", ".mp4", ".avi", ".mov", ".m4v", ".ts", ".wmv"}


class TorBoxAPI:
    @property
    def api_key(self) -> str:
        return get_setting("api_key", PREFIX)

    def is_enabled(self) -> bool:
        return get_setting("enabled", PREFIX) == "true"

    def is_authenticated(self) -> bool:
        return bool(self.api_key)

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}"}

    def _get(self, endpoint: str, params: dict[str, Any] | list[tuple[str, str]] | None = None) -> dict[str, Any]:
        response = requests.get(
            f"{BASE_URL}/{endpoint}", headers=self._headers(), params=params or {}, timeout=20
        )
        response.raise_for_status()
        return response.json()

    def _post(self, endpoint: str, data: dict[str, Any] | None = None) -> dict[str, Any]:
        response = requests.post(
            f"{BASE_URL}/{endpoint}", headers=self._headers(), data=data or {}, timeout=20
        )
        response.raise_for_status()
        return response.json() if response.content else {}

    def test_connection(self) -> bool:
        try:
            result = self._get("user/me")
            return bool(result.get("success"))
        except Exception:
            return False

    def add_magnet(self, magnet: str) -> dict[str, Any]:
        result = self._post("torrents/createtorrent", {"magnet": magnet, "seed": "3"})
        if result.get("success"):
            return result
        # Torrent already in user's list — look it up by hash so the caller can proceed
        hash_val = _extract_hash(magnet)
        if hash_val:
            existing = self.find_torrent_by_hash(hash_val)
            if existing:
                torrent_id = existing.get("id")
                return {"success": True, "data": {"torrent_id": torrent_id}}
        return result

    def get_torrent_info(self, torrent_id: int) -> dict[str, Any]:
        return self._get("torrents/mylist", {"id": str(torrent_id), "bypass_cache": "true"})

    def request_download(self, torrent_id: int, file_id: int) -> dict[str, Any]:
        return self._get("torrents/requestdl", {
            "token": self.api_key,
            "torrent_id": str(torrent_id),
            "file_id": str(file_id),
            "zip_link": "false",
        })

    def find_torrent_by_hash(self, hash_str: str) -> dict[str, Any] | None:
        try:
            result = self._get("torrents/mylist", {"bypass_cache": "true"})
            data = result.get("data") or []
            if isinstance(data, list):
                for t in data:
                    if isinstance(t, dict) and t.get("hash", "").lower() == hash_str.lower():
                        return t
        except Exception as e:
            log(str(e), "torbox.find_torrent_by_hash")
        return None

    def check_instant_availability(self, hashes: list[str]) -> set[str]:
        if not hashes:
            return set()
        cached: set[str] = set()
        for i in range(0, len(hashes), 100):
            chunk = hashes[i:i + 100]
            try:
                # TorBox requires repeated `hash` params, not comma-joined
                params: list[tuple[str, str]] = [("hash", h) for h in chunk]
                params += [("format", "list"), ("list_files", "false")]
                result = self._get("torrents/checkcached", params)
                data = result.get("data") or []
                if isinstance(data, list):
                    for h in data:
                        if isinstance(h, str):
                            cached.add(h.lower())
            except Exception as e:
                log(str(e), "torbox.check_instant_availability")
        return cached

    def pick_video_file(self, files: list[dict[str, Any]]) -> dict[str, Any] | None:
        if not files:
            return None
        video = [f for f in files if any(
            f.get("name", "").lower().endswith(ext) for ext in _VIDEO_EXTS
        )]
        return max(video or files, key=lambda f: f.get("size", 0))


def _extract_hash(magnet: str) -> str:
    """Extract the infohash from a magnet URI."""
    lower = magnet.lower()
    if "btih:" in lower:
        part = magnet[lower.index("btih:") + 5:]
        return part.split("&")[0]
    return ""


TorBox = TorBoxAPI()
