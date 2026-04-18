import xbmc
from xbmc import LOGDEBUG
import traceback


def logger(message: str, function: str = "function", log_level: int = LOGDEBUG):
    xbmc.log("[Bacterio]\n\t[%s]: %s" % (function, message), log_level)


def trace(heading: str):
    trace = traceback.format_stack()
    xbmc.log("[Bacterio]\n\t[%s]: %s" % (heading, "".join(trace)), 2)
