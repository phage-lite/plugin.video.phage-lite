import threading
from base64 import b64encode
from json import dumps
from typing import Any, final
import xbmc
import xbmcgui

from utils.logger import log

_WIN_ID = 10000
_PROP_TYPE    = "bacterio.type"
_PROP_TMDB    = "bacterio.tmdb_id"
_PROP_SEASON  = "bacterio.season"
_PROP_EPISODE = "bacterio.episode"

_IMG = "https://image.tmdb.org/t/p/"


# ── Next-episode helpers ──────────────────────────────────────────────────────

def _find_next(
    show_id: int, season: int, episode: int
) -> tuple[int, int, str, str, str, dict[str, str], dict[str, str]] | None:
    """Return (next_season, next_ep, next_title, curr_title, show_title, curr_art, next_art) or None."""
    from services.tmdb import Tmdb
    try:
        season_data = Tmdb.tv_season(show_id, season)
        episodes: list[dict[str, Any]] = season_data.get("episodes") or []
        ep_nums = {e["episode_number"] for e in episodes}

        curr_info = next((e for e in episodes if e["episode_number"] == episode), {})
        curr_title = curr_info.get("name") or f"Episode {episode}"

        next_ep, next_season = episode + 1, season
        ep_info: dict[str, Any] = {}

        if next_ep in ep_nums:
            ep_info = next((e for e in episodes if e["episode_number"] == next_ep), {})
        else:
            next_season, next_ep = season + 1, 1
            next_data = Tmdb.tv_season(show_id, next_season)
            next_eps: list[dict[str, Any]] = next_data.get("episodes") or []
            if not next_eps:
                return None
            ep_info = next((e for e in next_eps if e["episode_number"] == 1), {})

        show_details = Tmdb.tv_details(show_id)
        show_title = show_details.get("name", "")

        show_art: dict[str, str] = {}
        if poster := show_details.get("poster_path"):
            show_art["tvshow.poster"] = f"{_IMG}w500{poster}"
        if backdrop := show_details.get("backdrop_path"):
            show_art["tvshow.fanart"] = f"{_IMG}w780{backdrop}"

        curr_art = dict(show_art)
        if curr_still := curr_info.get("still_path"):
            curr_art["thumb"] = f"{_IMG}w500{curr_still}"

        next_art = dict(show_art)
        if next_still := ep_info.get("still_path"):
            next_art["thumb"] = f"{_IMG}w500{next_still}"

        next_title = ep_info.get("name") or f"Episode {next_ep}"
        return next_season, next_ep, next_title, curr_title, show_title, curr_art, next_art
    except Exception as e:
        log(f"find_next_error {e}")
        return None


def _build_episode(
    show_id: int, season: int, episode: int, title: str,
    show_title: str, art: dict[str, str]
) -> dict[str, Any]:
    return {
        "episodeid": -1,
        "tvshowid": str(show_id),
        "title": title,
        "season": str(season),
        "episode": str(episode),
        "showtitle": show_title,
        "plot": "",
        "playcount": 0,
        "rating": 0,
        "firstaired": "",
        "runtime": 0,
        "art": art,
    }


# ── Player ────────────────────────────────────────────────────────────────────

@final
class _Player(xbmc.Player):
    def __init__(self):
        super().__init__()
        self._meta: dict[str, str] | None = None
        self._last_progress: float = 0.0
        self._monitor_alive: bool = False

    def _read_meta(self) -> dict[str, str] | None:
        win = xbmcgui.Window(_WIN_ID)
        tmdb_id = win.getProperty(_PROP_TMDB)
        if not tmdb_id:
            return None
        return {
            "type":    win.getProperty(_PROP_TYPE) or "movie",
            "tmdb_id": tmdb_id,
            "season":  win.getProperty(_PROP_SEASON) or "0",
            "episode": win.getProperty(_PROP_EPISODE) or "0",
        }

    def _progress(self) -> float:
        try:
            total = self.getTotalTime()
            if total > 0:
                return min(self.getTime() / total * 100.0, 100.0)
        except Exception:
            pass
        return 0.0

    def _scrobble(self, action: str, progress: float) -> None:
        if not self._meta:
            return
        try:
            from services.trakt import Trakt
            if not Trakt.is_authenticated:
                return
            m = self._meta
            log(f"scrobble {action} {m['type']} id={m['tmdb_id']} s={m['season']} e={m['episode']} p={progress:.1f}", "service")
            Trakt.scrobble(action, m["type"], int(m["tmdb_id"]), progress,
                           int(m["season"]), int(m["episode"]))
        except Exception as e:
            log(str(e), "service._scrobble")

    def _start_monitor(self) -> None:
        if not self._monitor_alive:
            self._monitor_alive = True
            threading.Thread(target=self._monitor, daemon=True).start()

    def _monitor(self) -> None:
        log("monitor started", "service")
        try:
            while self.isPlayingVideo():
                if self._meta is None:
                    self._meta = self._read_meta()
                    if self._meta:
                        log(f"meta acquired: {self._meta}", "service")
                p = self._progress()
                if p > 0:
                    self._last_progress = p
                xbmc.sleep(1000)
        finally:
            self._monitor_alive = False
            log("monitor stopped", "service")

    def _send_upnext_signal(self, meta: dict[str, str]) -> None:
        if not xbmc.getCondVisibility("System.HasAddon(service.upnext)"):
            return

        show_id = int(meta["tmdb_id"])
        season  = int(meta["season"])
        episode = int(meta["episode"])

        result = _find_next(show_id, season, episode)
        if not result:
            log("upnext: no next episode found", "service")
            return
        next_season, next_ep, next_title, curr_title, show_title, curr_art, next_art = result

        next_info = {
            "current_episode": _build_episode(show_id, season, episode, curr_title, show_title, curr_art),
            "next_episode":    _build_episode(show_id, next_season, next_ep, next_title, show_title, next_art),
            "play_url": (
                "plugin://plugin.video.bacterio"
                f"?action=play&type=episode&id={show_id}"
                f"&season={next_season}&episode={next_ep}"
            ),
        }

        data = str(b64encode(dumps(next_info).encode()), "utf-8")
        xbmc.executeJSONRPC(dumps({
            "jsonrpc": "2.0",
            "id": 0,
            "method": "JSONRPC.NotifyAll",
            "params": {
                "sender": "plugin.video.bacterio.SIGNAL",
                "message": "upnext_data",
                "data": [data],
            },
        }))
        log(f"upnext signal sent: s{next_season}e{next_ep} '{next_title}'", "service")

    def onPlayBackStarted(self):
        log("onPlayBackStarted", "service")
        self._meta = self._read_meta()
        self._scrobble("start", 0.0)
        self._start_monitor()

    def onAVStarted(self):
        log("onAVStarted", "service")
        if self._meta is None:
            self._meta = self._read_meta()
        self._start_monitor()
        if self._meta and self._meta.get("type") == "episode":
            threading.Thread(target=self._send_upnext_signal, args=(self._meta,), daemon=True).start()

    def onPlayBackPaused(self):
        self._scrobble("pause", self._progress())

    def onPlayBackResumed(self):
        self._scrobble("start", self._progress())

    def onPlayBackEnded(self):
        self._scrobble("stop", 100.0)
        self._meta = None
        self._last_progress = 0.0

    def onPlayBackStopped(self):
        self._scrobble("stop", self._last_progress)
        self._meta = None
        self._last_progress = 0.0

    def onPlayBackError(self):
        self._meta = None


# ── Monitor ───────────────────────────────────────────────────────────────────

@final
class _Monitor(xbmc.Monitor):
    def __init__(self):
        super().__init__()
        self._player = _Player()

    def run(self) -> None:
        while not self.abortRequested():
            if self.waitForAbort(10):
                break


if __name__ == "__main__":
    _Monitor().run()
