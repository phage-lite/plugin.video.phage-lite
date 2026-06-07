import re
import requests
from typing import Any

from utils.logger import log

_BASE = "https://torrentio.strem.fun"
_TIMEOUT = 10
_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}

_QUALITY_PATTERNS: dict[str, list[str]] ={ 
        "4K": ["2160", "4K", "UHD"],
        "1080p": ["1080", "HD"],
        "720p": ["720"],
        "CAM": ["CAM", "HDCAM"],
        "TELE": ["TELE"],
        "SYNC": ["SYNC"]
}

_LANG_PATTERNS: dict[str, list[str]] = {
        "EN": [],
        "FR": ["french", "truefrench", "vostfr", "vff", "vfq"],
        "ES": ["spanish", "espanol"],
        "IT": ["italian"],
        "PT": ["portuguese", "portugues"],
        "PL": ["polish", "PL"],
        "TR": ["turkish", "TR"],
        "RU": ["russian", "RU"],
        "NL": ["nederlands", "dutch", "nl"],
        "DE": ["deutsch", "german", "de", "GER"],
        "AR": ["arabic", "ar"],
        "HI": ["hindi", "hi"],
}

def scrape(imdb_id: str, season: int = 0, episode: int = 0) -> list[dict[str, Any]]:
    if season:
        url = f"{_BASE}/stream/series/{imdb_id}:{season}:{episode}.json"
    else:
        url = f"{_BASE}/stream/movie/{imdb_id}.json"
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT)
        resp.raise_for_status()
        streams: list[dict[str, Any]] = resp.json().get("streams") or []
    except Exception as e:
        log(str(e), "torrentio.scrape")
        return []

    results: list[dict[str, Any]] = []
    for st in streams:
        parsed = _parse_stream(st)
        if parsed:
            results.append(parsed)
    return results


def _parse_stream(st: dict[str, Any]) -> dict[str, Any] | None:
    hash = (st.get("infoHash") or "").lower()
    if len(hash) != 40:
        return None

    title_block = st.get("title") or ""
    lines = title_block.splitlines()
    name = lines[0].strip() if lines else (st.get("name") or "")
    seeders = _extract_int(r"👤\s*(\d+)", title_block)
    size_gb = _extract_size(title_block)
    quality = _detect_quality(name)
    language = _detect_language(name)

    return {
        "provider": "Torrentio",
        "source": "torrent",
        "hash": hash,
        "url": f"magnet:?xt=urn:btih:{hash}&dn={requests.utils.quote(name)}",
        "name": name,
        "quality": quality,
        "language": language,
        "seeders": seeders,
        "size": size_gb,
        "debridonly": True,
    }

def _extract_int(pattern: str, text: str) -> int:
    m = re.search(pattern, text)
    return int(m.group(1)) if m else 0


def _extract_size(text: str) -> float:
    m = re.search(r"([\d.]+)\s*(GB|GiB|MB|MiB)", text, re.I)
    if not m:
        return 0.0
    val = float(m.group(1))
    return round(val / 1024, 2) if m.group(2).upper().startswith("M") else val

def _detect_language(name: str) ->str:
    upper = name.upper()
    for lang, patterns in _LANG_PATTERNS.items():
        if any(p in upper for p in patterns):
            return lang
    return "EN"

def _detect_quality(name: str) -> str:
    upper = name.upper()
    for quality, patterns in _QUALITY_PATTERNS.items():
        if any(p in upper for p in patterns):
            return quality
    return "SD"
