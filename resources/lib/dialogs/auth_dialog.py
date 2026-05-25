from typing import Any, cast
from typing_extensions import override
import xbmcgui
import xbmcaddon

CONTROL_QR = 1
CONTROL_LABEL = 2
CONTROL_TITLE = 3
CONTROL_CANCEL = 100

class AuthDialog(xbmcgui.WindowXMLDialog):
    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.title: str = "Authenticate"
        self.qr_path: str = ""
        self.message: str = ""
        self.cancelled: bool = False

    @override
    def onInit(self):
        cast(xbmcgui.ControlLabel, self.getControl(CONTROL_TITLE)).setLabel(self.title)
        cast(xbmcgui.ControlImage, self.getControl(CONTROL_QR)).setImage(self.qr_path)
        cast(xbmcgui.ControlLabel, self.getControl(CONTROL_LABEL)).setLabel(self.message)

    @override
    def onClick(self, controlId: int):
        if controlId == CONTROL_CANCEL:
            self.cancelled = True
            self.close()


def create_auth_dialog(qr_path: str, message: str) -> AuthDialog:
    dialog = AuthDialog(
        "auth_dialog.xml",
        xbmcaddon.Addon().getAddonInfo("path"),
        "default",
        "1080i",
    )
    dialog.qr_path = qr_path
    dialog.message = message
    return dialog
