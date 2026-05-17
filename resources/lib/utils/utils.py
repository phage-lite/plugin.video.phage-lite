import time
from typing import TypeVar
import xbmcaddon

T = TypeVar("T")


def make_qrcode(url: str):
    from segno import make
    from os import path

    try:
        art_path = path.join(
            xbmcaddon.Addon().getAddonInfo("path"), f"qr_{int(time.time())}.png"
        )
        qrcode = make(url, micro=False)
        qrcode.save(art_path, scale=20)
    except Exception:
        raise Exception("Could not create qrcode")
    return art_path


def make_tinyurl(url: str):
    import requests

    short_url = ""
    try:
        tiny_url = "http://tinyurl.com/api-create.php"
        response = requests.get(tiny_url, params={"url": url})
        status = response.status_code
        if status == 200:
            short_url = response.text
        else:
            pass
    except Exception:
        pass
    return short_url


def unwrap(value: T | None, label: str = "value") -> T:
    if value is None:
        raise Exception(label + " cannot be None")
    return value
