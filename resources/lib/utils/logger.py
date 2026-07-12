import xbmc
from xbmc import LOGDEBUG, LOGERROR, LOGINFO, LOGWARNING
import traceback


def log(message: str, function: str = "function", log_level: int = LOGINFO):
    xbmc.log("[Bacterio]\n\t[%s]: %s" % (function, message), log_level)


def debug(message: str, function: str = "function"):
    log(function, message, LOGDEBUG)


def warn(message: str, function: str = "function"):
    log(function, message, LOGWARNING)

def err(message: str, function: str = "function"):
    log(function, message, LOGERROR)

def trace(heading: str, log_level: int = LOGINFO):
    trace = traceback.format_stack()
    xbmc.log("[Bacterio]\n\t[%s]: %s" % (heading, "".join(trace)), log_level)
