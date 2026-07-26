import threading
from base64 import b64encode
from json import dumps
from typing import Any, final
import xbmc
import xbmcgui

from services.tmdb import Tmdb
from utils.router import url
from utils.logger import debug, err, log

_WIN_ID = 10000
_PROP_TYPE = "bacterio.type"
_PROP_TMDB = "bacterio.tmdb_id"
_PROP_SEASON = "bacterio.season"
_PROP_EPISODE = "bacterio.episode"


def _find_next(
    show_id: int, season: int, episode: int
) -> dict[str, dict[str, Any] | str] | None:
    from services.tmdb import Tmdb

    try:
        show_details = Tmdb.tv_show_details(show_id)

        season_data = Tmdb.tv_season(show_id, season)
        episodes: list[dict[str, Any]] = season_data.get("episodes") or []
        ep_nums = {e["episode_number"] for e in episodes}

        curr_info: dict[str, Any] = next((e for e in episodes if e["episode_number"] == episode), {})

        current_episode = _build_episode(curr_info, show_details)

        next_ep, next_season = episode + 1, season
        next_ep_info: dict[str, Any] = {}

        if next_ep in ep_nums:
            next_ep_info = next(
                (e for e in episodes if e["episode_number"] == next_ep), {}
            )
        else:
            next_season, next_ep = season + 1, 1
            next_data = Tmdb.tv_season(show_id, next_season)
            next_eps: list[dict[str, Any]] = next_data.get("episodes") or []
            if not next_eps:
                return None
            next_ep_info = next((e for e in next_eps if e["episode_number"] == 1), {})

        next_episode = _build_episode(next_ep_info, show_details)

        return {
            "current_episode": current_episode,
            "next_episode": next_episode,
            "play_url": url("/play/", type="episode", id=show_id, season=next_season, episode=next_ep)
        }
    except Exception as e:
        err(f"find_next_error {e}")
        return None


def _build_episode(
    episode_details: dict[str, Any], show_details: dict[str, Any]
) -> dict[str, Any]:
    images = show_details.get("images", {})
    clearlogodata: dict[str, Any] = next((i for i in images["logos"]), { "file_path": "" },)
    clearlogo = clearlogodata.get("file_path")

    return {
        "episodeid": str(episode_details.get("id", -1)),
        "tvshowid": str(show_details.get("id", -1)),
        "title": str(episode_details.get("name", "Episode")),
        "season": str(episode_details.get("season_number", -1)),
        "episode": str(episode_details.get("episode_number", -1)),
        "showtitle": str(show_details.get("name", "")),
        "plot": str(episode_details.get("overview", "")),
        "playcount": int(episode_details.get("vote_count", 0)),
        "rating": int(episode_details.get("vote_average", 0)),
        "firstaired": str(episode_details.get("air_date", "1999-12-31")),
        "runtime": int(episode_details.get("runtime") or 30) * 60,
        "art": {
            "thumb": Tmdb.get_image_url(str(episode_details.get("still_path"))),
            "tvshow.clearart": Tmdb.get_image_url(str(show_details.get("backdrop_path")), "w1280"),
            "tvshow.clearlogo": Tmdb.get_image_url(str(clearlogo)),
            "tvshow.fanart": Tmdb.get_image_url(str(show_details.get("backdrop_path")), "w1280"),
            "tvshow.landscape": Tmdb.get_image_url(str(episode_details.get("still_path")), "w1280"),
            "tvshow.poster": Tmdb.get_image_url(str(show_details.get("poster_path")), "w780"),
        },
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
            "type": win.getProperty(_PROP_TYPE) or "movie",
            "tmdb_id": tmdb_id,
            "season": win.getProperty(_PROP_SEASON) or "0",
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
            debug(
                f"scrobble {action} {m['type']} id={m['tmdb_id']} s={m['season']} e={m['episode']} p={progress:.1f}",
                "service",
            )
            Trakt.scrobble(
                action,
                m["type"],
                int(m["tmdb_id"]),
                progress,
                int(m["season"]),
                int(m["episode"]),
            )
        except Exception as e:
            err(str(e), "service._scrobble")

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
                        debug(f"meta acquired: {self._meta}", "service")
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
        season = int(meta["season"])
        episode = int(meta["episode"])

        result = _find_next(show_id, season, episode)
        if not result:
            log("upnext: no next episode found", "service")
            return

        data = str(b64encode(dumps(result).encode()), "utf-8")
        _ = xbmc.executeJSONRPC(
            dumps(
                {
                    "jsonrpc": "2.0",
                    "id": 0,
                    "method": "JSONRPC.NotifyAll",
                    "params": {
                        "sender": "plugin.video.bacterio.SIGNAL",
                        "message": "upnext_data",
                        "data": [data],
                    },
                }
            )
        )
        debug(f"upnext signal sent: s{season}e{episode} '{show_id}'", "service")

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
            threading.Thread(
                target=self._send_upnext_signal, args=(self._meta,), daemon=True
            ).start()

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
