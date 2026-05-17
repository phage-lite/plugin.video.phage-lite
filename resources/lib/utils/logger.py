import xbmc
from xbmc import LOGINFO
import traceback


def log(message: str, function: str = "function", log_level: int = LOGINFO):
    xbmc.log("[Bacterio]\n\t[%s]: %s" % (function, message), log_level)


def trace(heading: str, log_level: int = LOGINFO):
    trace = traceback.format_stack()
    xbmc.log("[Bacterio]\n\t[%s]: %s" % (heading, "".join(trace)), log_level)
