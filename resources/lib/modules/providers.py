# -*- coding: utf-8 -*-
# Central registry for provider names, scraper IDs, quality labels, and API paths.
# All other modules import from here — never hardcode these strings elsewhere.

# ── Debrid provider display names ─────────────────────────────────────────────
REAL_DEBRID = "Real-Debrid"

DEBRID_PROVIDERS = (REAL_DEBRID)

# ── Debrid short codes (settings keys / cache keys) ───────────────────────────
RD = "rd"

# name → short code pairs used in enabled-debrid checks
PROVIDER_CODES = (
    (REAL_DEBRID, RD),
)

# ── Internal scraper / cloud IDs ──────────────────────────────────────────────
FOLDERS  = "folders"
EXTERNAL = "external"

RD_CLOUD  = "rd_cloud"

RD_BROWSE = "rd_browse"

DEFAULT_SCRAPERS = (RD_CLOUD, FOLDERS)

# ── Quality labels ─────────────────────────────────────────────────────────────
Q_4K   = "4K"
Q_1080 = "1080p"
Q_720  = "720p"
Q_SD   = "SD"
Q_SCR  = "SCR"
Q_CAM  = "CAM"
Q_TELE = "TELE"

QUALITIES            = (Q_4K, Q_1080, Q_720, Q_SD)
PRERELEASE_QUALITIES = (Q_SCR, Q_CAM, Q_TELE)
ALL_QUALITIES        = QUALITIES + PRERELEASE_QUALITIES

# ── API module mapping: scraper/provider ID → (module_path, class_name) ───────
DEBRID_MODULES = {
    REAL_DEBRID: ("apis.real_debrid_api", "RealDebridAPI"),
    RD_CLOUD:    ("apis.real_debrid_api", "RealDebridAPI"),
    RD_BROWSE:   ("apis.real_debrid_api", "RealDebridAPI"),
}

# ── Debrid icon names (used in downloader) ────────────────────────────────────
DEBRID_ICONS = {
    REAL_DEBRID: "realdebrid",
}
