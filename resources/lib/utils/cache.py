import hashlib
import json
import os
import time
from typing import Any

import xbmcvfs

_DIR = xbmcvfs.translatePath(
    "special://profile/addon_data/plugin.video.bacterio/cache/"
)


def _path(key: str) -> str:
    return os.path.join(_DIR, hashlib.md5(key.encode()).hexdigest() + ".json")


def get(key: str, ttl: int) -> Any | None:
    try:
        with open(_path(key)) as f:
            data = json.load(f)
        if time.time() - data["ts"] < ttl:
            return data["v"]
    except Exception:
        pass
    return None


def set(key: str, value: Any) -> None:
    os.makedirs(_DIR, exist_ok=True)
    try:
        with open(_path(key), "w") as f:
            json.dump({"ts": time.time(), "v": value}, f)
    except Exception:
        pass


def clear() -> int:
    count = 0
    try:
        for name in os.listdir(_DIR):
            if name.endswith(".json"):
                os.remove(os.path.join(_DIR, name))
                count += 1
    except Exception:
        pass
    return count
