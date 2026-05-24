import threading
import xbmc
import xbmcgui

_WIN_ID = 10000
_PROP_TYPE = "bacterio.type"
_PROP_TMDB = "bacterio.tmdb_id"
_PROP_SEASON = "bacterio.season"
_PROP_EPISODE = "bacterio.episode"

_NEXT_UP_DELAY = 2000   # ms after playback ends before showing dialog
_NEXT_UP_SECS = 10      # countdown seconds


# ── Next-episode helpers ──────────────────────────────────────────────────────

def _find_next(show_id: int, season: int, episode: int) -> tuple[int, int, str, str] | None:
    """Return (next_season, next_ep, ep_title, show_title) or None."""
    from services.tmdb import Tmdb
    try:
        season_data = Tmdb.tv_season(show_id, season)
        ep_nums = sorted(e["episode_number"] for e in season_data.get("episodes", []))

        next_ep = episode + 1
        next_season = season
        ep_info: dict = {}

        if next_ep in ep_nums:
            ep_info = next((e for e in season_data["episodes"] if e["episode_number"] == next_ep), {})
        else:
            next_season = season + 1
            next_ep = 1
            next_data = Tmdb.tv_season(show_id, next_season)
            next_episodes = next_data.get("episodes", [])
            if not next_episodes:
                return None
            ep_info = next((e for e in next_episodes if e["episode_number"] == 1), {})

        ep_title = ep_info.get("name") or f"Episode {next_ep}"
        show_title = Tmdb.tv_details(show_id).get("name", "")
        return next_season, next_ep, ep_title, show_title
    except Exception:
        return None


def _countdown(show_title: str, season: int, episode: int, ep_title: str) -> bool:
    label = f"S{season:02d}E{episode:02d}  ·  {ep_title}"
    steps = _NEXT_UP_SECS * 10
    dlg = xbmcgui.DialogProgress()
    dlg.create("Up Next", f"{show_title}\n{label}")
    for i in range(steps, -1, -1):
        pct = int(i / steps * 100)
        secs_left = (i + 9) // 10
        dlg.update(pct, f"{show_title}\n{label}\n\nPlaying in {secs_left}s  ·  Back to cancel")
        if dlg.iscanceled():
            dlg.close()
            return False
        xbmc.sleep(100)
    dlg.close()
    return True


# ── Player ────────────────────────────────────────────────────────────────────

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

    def _maybe_play_next(self, meta: dict[str, str]) -> None:
        xbmc.sleep(_NEXT_UP_DELAY)
        try:
            show_id = int(meta["tmdb_id"])
            season = int(meta["season"])
            episode = int(meta["episode"])
            result = _find_next(show_id, season, episode)
            if not result:
                return
            next_season, next_ep, ep_title, show_title = result
            if not _countdown(show_title, next_season, next_ep, ep_title):
                return
            url = (
                f"plugin://plugin.video.bacterio"
                f"?action=play&type=episode&id={show_id}"
                f"&season={next_season}&episode={next_ep}"
            )
            xbmc.executebuiltin(f"RunPlugin({url})")
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
        meta = self._meta
        self._meta = None
        if meta and meta.get("type") == "episode":
            threading.Thread(target=self._maybe_play_next, args=(meta,), daemon=True).start()

    def onPlayBackStopped(self):
        self._scrobble("stop", self._progress())
        self._meta = None

    def onPlayBackError(self):
        self._meta = None


# ── Monitor ───────────────────────────────────────────────────────────────────

class _Monitor(xbmc.Monitor):
    def __init__(self):
        super().__init__()
        self._player = _Player()

    def run(self) -> None:
        while not self.waitForAbort(60):
            pass


if __name__ == "__main__":
    _Monitor().run()
