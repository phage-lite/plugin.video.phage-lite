import xbmc
import xbmcgui

_WIN_ID = 10000
_PROP_TYPE = "bacterio.type"
_PROP_TMDB = "bacterio.tmdb_id"
_PROP_SEASON = "bacterio.season"
_PROP_EPISODE = "bacterio.episode"


class _Player(xbmc.Player):
    def __init__(self):
        super().__init__()
        self._meta: dict[str, str] | None = None

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
            if not Trakt.is_authenticated():
                return
            m = self._meta
            Trakt.scrobble(
                action,
                m["type"],
                int(m["tmdb_id"]),
                progress,
                int(m["season"]),
                int(m["episode"]),
            )
        except Exception:
            pass

    def onPlayBackStarted(self):
        self._meta = self._read_meta()
        self._scrobble("start", 0.0)

    def onPlayBackPaused(self):
        self._scrobble("pause", self._progress())

    def onPlayBackResumed(self):
        self._scrobble("start", self._progress())

    def onPlayBackEnded(self):
        self._scrobble("stop", 100.0)
        self._meta = None

    def onPlayBackStopped(self):
        self._scrobble("stop", self._progress())
        self._meta = None

    def onPlayBackError(self):
        self._meta = None


class _Monitor(xbmc.Monitor):
    def __init__(self):
        super().__init__()
        self._player = _Player()

    def run(self) -> None:
        while not self.waitForAbort(60):
            pass


if __name__ == "__main__":
    _Monitor().run()
