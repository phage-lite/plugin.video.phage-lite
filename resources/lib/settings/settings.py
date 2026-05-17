import xbmcaddon
import xbmcgui

_addon = xbmcaddon.Addon()
_window = xbmcgui.Window(10000)

_PREFIX = "bacterio."


def _sid(setting_id: str) -> str:
    if setting_id and setting_id.startswith(_PREFIX):
        return setting_id[len(_PREFIX) :]
    return setting_id


def _prop(setting_id: str) -> str:
    return f"{_PREFIX}{_sid(setting_id)}"


def get_setting(setting_id: str, prefix: str = "", fallback: str = ""):
    if (prefix):
        setting_id = f"{prefix}.{setting_id}"
    sid = _sid(setting_id)
    cached = _window.getProperty(_prop(sid))
    if cached:
        return cached
    value = _addon.getSetting(sid)
    if value:
        _window.setProperty(_prop(sid), value)
        return value
    return fallback


def set_setting(setting_id: str, value: object, prefix: str = ""):
    if (prefix):
        setting_id = f"{prefix}.{setting_id}"
    sid = _sid(setting_id)
    _addon.setSetting(sid, str(value))
    _window.setProperty(_prop(sid), str(value))
