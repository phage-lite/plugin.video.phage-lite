import os
import sys
import threading
import xbmc
import xbmcgui

from services.config import get_service
from services.types import PollStatus
from dialogs.auth_dialog import create_auth_dialog
from utils.logger import log
from utils.utils import make_qrcode, make_tinyurl


def _test_torbox() -> None:
    from services.torbox import TorBox
    if not TorBox.access_token:
        _ = xbmcgui.Dialog().ok("TorBox", "No API key set.\n\nGo to Settings → TorBox and enter your API key.")
        return
    if TorBox.test_connection():
        xbmcgui.Dialog().notification("TorBox", "Connected successfully!", time=3000)
    else:
        _ = xbmcgui.Dialog().ok("TorBox", "Could not connect. Please check your API key.")


def _test_tmdb() -> None:
    import requests
    from settings.settings import get_setting
    from settings.ids import SettingID as SID
    token = get_setting(SID.CLIENT_SECRET, "tmdb")
    if not token:
        _ = xbmcgui.Dialog().ok("TMDB", "No API Bearer token set.\n\nGo to Settings → TMDB and enter your Read Access Token.")
        return
    try:
        resp = requests.get(
            "https://api.themoviedb.org/3/authentication",
            headers={"Authorization": f"Bearer {token}", "accept": "application/json"},
            timeout=10,
        )
        if resp.ok and resp.json().get("success"):
            xbmcgui.Dialog().notification("TMDB", "Connected successfully!", time=3000)
        else:
            _ = xbmcgui.Dialog().ok("TMDB", f"Authentication failed.\n\nCheck your Read Access Token in Settings → TMDB.\n\n{resp.status_code}")
    except Exception as e:
        _ = xbmcgui.Dialog().ok("TMDB", f"Could not connect to TMDB.\n\n{e}")


def main():
    service_arg = sys.argv[1]

    if service_arg == "clear_cache":
        from utils import cache
        from utils.notifications import info
        n = cache.clear()
        info(f"Cache cleared ({n} files)")
        return

    if service_arg == "tmdb":
        _test_tmdb()
        return

    service = get_service(service_arg)
    auth_data = service.start_auth()

    verification_url = auth_data.get("verification_url")
    direct_verification_url = auth_data.get("direct_verification_url")
    user_code = auth_data.get("user_code")
    interval = auth_data.get("interval") or 5

    result: list[PollStatus] = [PollStatus.PENDING]
    event = threading.Event()

    def poll_loop():
        while not event.is_set():
            xbmc.sleep(interval * 1000)
            status = service.poll()
            if status != PollStatus.PENDING:
                result[0] = status
                event.set()
                os.remove(qr_code)
                dialog.close()

    qr_code = make_qrcode(direct_verification_url) or ""
    tiny_url = make_tinyurl(direct_verification_url) or ""
    dialog = create_auth_dialog(
        qr_code,
        f"Visit: [B]{verification_url}[/B] and enter: [B]{user_code}[/B] or go directly to: [B]{tiny_url}[/B]"
    )
    thread = threading.Thread(target=poll_loop)
    thread.start()

    dialog.doModal()
    event.set()

    if result[0] == PollStatus.SUCCESS:
        service.auth_complete()

main()
