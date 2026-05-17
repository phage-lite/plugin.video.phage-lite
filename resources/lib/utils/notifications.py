import xbmcgui


def error(message: str, title: str = "Bacterio"):
    xbmcgui.Dialog().notification(title, message, xbmcgui.NOTIFICATION_ERROR)


def info(message: str, title: str = "Bacterio"):
    xbmcgui.Dialog().notification(title, message, xbmcgui.NOTIFICATION_INFO)


def warn(message: str, title: str = "Bacterio"):
    xbmcgui.Dialog().notification(title, message, xbmcgui.NOTIFICATION_WARNING)
