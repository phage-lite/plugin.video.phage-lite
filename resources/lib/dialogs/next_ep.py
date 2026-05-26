from typing import Any, cast
import xbmcgui
import xbmcaddon

CONTROL_HEADER = 1
CONTROL_BODY = 2
CONTROL_PLAY = 11
CONTROL_CLOSE = 10
CONTROL_CANCEL = 12

class NextUpWidget(xbmcgui.WindowXMLDialog):
    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.title: str = "Next Up"
        self.header: str = ""
        self.body: str = ""
        self.cancelled: bool = False
        self.skip: bool = False

    def onInit(self):
        cast(xbmcgui.ControlLabel, self.getControl(CONTROL_HEADER)).setLabel(self.header)
        cast(xbmcgui.ControlLabel, self.getControl(CONTROL_BODY)).setLabel(self.body)

    def onAction(self, action: xbmcgui.Action) -> None:
        if action.getId() in (9, 10, 92):  # Back / PreviousMenu / NavBack
            self.cancelled = True
            self.close()

    def onClick(self, controlId: int):
        if controlId == CONTROL_CANCEL:
            self.cancelled = True
            self.close()
        if controlId == CONTROL_CLOSE:
            self.close()
        if controlId == CONTROL_PLAY:
            self.skip = True
            self.close()


def create_next_ep_widget(show_title: str, season: int, episode: int, ep_title: str) -> NextUpWidget:
    dialog = NextUpWidget(
        "next_ep.xml",
        xbmcaddon.Addon().getAddonInfo("path"),
        "default",
        "1080i",
    )
    dialog.header = f"[B]Up Next  ·  S{season:02d}E{episode:02d}[/B]  {ep_title}"
    dialog.body = f"[I]{show_title}[/I]"
    return dialog
