import threading
from typing import Any, final
import xbmc
import xbmcgui

from dialogs.next_ep import create_next_ep_widget
from utils.logger import log

_WIN_ID = 10000
_PROP_TYPE    = "bacterio.type"
_PROP_TMDB    = "bacterio.tmdb_id"
_PROP_SEASON  = "bacterio.season"
_PROP_EPISODE = "bacterio.episode"

_THRESHOLD_SECS = 80   # seconds before end to trigger (when no chapters)
_COUNTDOWN_SECS = 20   # how long the widget stays visible


# ── Next-episode helpers ──────────────────────────────────────────────────────

def _near_end(player: xbmc.Player) -> bool:
    try:
        total = player.getTotalTime()
        if total <= 0:
            return False
        return (total - player.getTime()) <= _THRESHOLD_SECS
    except Exception as e:
        log(f"near_end_error {e}")
        return False


def _find_next(show_id: int, season: int, episode: int) -> tuple[int, int, str, str] | None:
    """Return (next_season, next_ep, ep_title, show_title) or None."""
    from services.tmdb import Tmdb
    try:
        season_data = Tmdb.tv_season(show_id, season)
        ep_nums = {e["episode_number"] for e in season_data.get("episodes", [])}

        next_ep, next_season = episode + 1, season
        _empty: dict[str, Any] = {}
        ep_info: dict[str, Any] = _empty

        if next_ep in ep_nums:
            episodes: list[dict[str, Any]] = season_data.get("episodes") or []
            ep_info = next((e for e in episodes if e["episode_number"] == next_ep), _empty)
        else:
            next_season, next_ep = season + 1, 1
            next_data = Tmdb.tv_season(show_id, next_season)
            next_eps: list[dict[str, Any]] = next_data.get("episodes") or []
            if not next_eps:
                return None
            ep_info = next((e for e in next_eps if e["episode_number"] == 1), _empty)

        ep_title = ep_info.get("name") or f"Episode {next_ep}"
        show_title = Tmdb.tv_details(show_id).get("name", "")
        return next_season, next_ep, ep_title, show_title
    except Exception as e:
        log(f"find_next_error {e}")
        return None


# ── Small overlay widget ──────────────────────────────────────────────────────

def _run_widget(meta: dict[str, str]) -> None:
    from utils.logger import log
    show_id = int(meta["tmdb_id"])
    season  = int(meta["season"])
    episode = int(meta["episode"])

    log(f"_run_widget show={show_id} s={season} e={episode}", "service")
    result = _find_next(show_id, season, episode)
    if not result:
        log("_find_next returned None - no widget", "service")
        return
    next_season, next_ep, ep_title, show_title = result

    widget = create_next_ep_widget(show_title, next_season, next_ep, ep_title)
    widget.doModal()

    steps = _COUNTDOWN_SECS * 5  # update every 200 ms
    for i in range(steps, -1, -1):
        if widget.cancelled:
            return
        if widget.skip:
            widget.close()

            url = (
                "plugin://plugin.video.bacterio"
                f"?action=play&type=episode&id={show_id}"
                f"&season={next_season}&episode={next_ep}"
            )
            xbmc.executebuiltin(f"RunPlugin({url})")
            return
        xbmc.sleep(200)

    widget.close()

    url = (
        "plugin://plugin.video.bacterio"
        f"?action=play&type=episode&id={show_id}"
        f"&season={next_season}&episode={next_ep}"
    )
    xbmc.executebuiltin(f"RunPlugin({url})")


# ── Player ────────────────────────────────────────────────────────────────────

@final
class _Player(xbmc.Player):
    def __init__(self):
        super().__init__()
        self._meta: dict[str, str] | None = None
        self._next_shown: bool = False
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
            from utils.logger import log
            if not Trakt.is_authenticated:
                return
            m = self._meta
            log(f"scrobble {action} {m['type']} id={m['tmdb_id']} s={m['season']} e={m['episode']} p={progress:.1f}", "service")
            Trakt.scrobble(action, m["type"], int(m["tmdb_id"]), progress,
                           int(m["season"]), int(m["episode"]))
        except Exception as e:
            from utils.logger import log
            log(str(e), "service._scrobble")

    def _start_monitor(self) -> None:
        if not self._monitor_alive:
            self._monitor_alive = True
            threading.Thread(target=self._monitor, daemon=True).start()

    def _monitor(self) -> None:
        """Polls position; fires next-up widget near episode end."""
        from utils.logger import log
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
                if (not self._next_shown
                        and self._meta
                        and self._meta.get("type") == "episode"
                        and _near_end(self)):
                    log("near end - launching widget", "service")
                    self._next_shown = True
                    meta = self._meta
                    threading.Thread(target=_run_widget, args=(meta,), daemon=True).start()
                xbmc.sleep(1000)
        finally:
            self._monitor_alive = False
            log("monitor stopped", "service")

    def onPlayBackStarted(self):
        from utils.logger import log
        log("onPlayBackStarted", "service")
        self._meta = self._read_meta()
        self._next_shown = False
        self._scrobble("start", 0.0)
        self._start_monitor()

    def onAVStarted(self):
        from utils.logger import log
        log("onAVStarted", "service")
        if self._meta is None:
            self._meta = self._read_meta()
        self._start_monitor()

    def onPlayBackPaused(self):
        self._scrobble("pause", self._progress())

    def onPlayBackResumed(self):
        self._scrobble("start", self._progress())

    def onPlayBackEnded(self):
        self._scrobble("stop", 100.0)
        self._meta = None
        self._next_shown = False
        self._last_progress = 0.0

    def onPlayBackStopped(self):
        self._scrobble("stop", self._last_progress)
        self._meta = None
        self._next_shown = False
        self._last_progress = 0.0

    def onPlayBackError(self):
        self._meta = None
        self._next_shown = False


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
