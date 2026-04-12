# -*- coding: utf-8 -*-
# Central registry for provider names, scraper IDs, quality labels, and API paths.
# All other modules import from here — never hardcode these strings elsewhere.

# ── Debrid provider display names ─────────────────────────────────────────────
REAL_DEBRID = "Real-Debrid"
PREMIUMIZE  = "Premiumize.me"
ALLDEBRID   = "AllDebrid"
EASYDEBRID  = "EasyDebrid"
TORBOX      = "TorBox"

DEBRID_PROVIDERS = (REAL_DEBRID, PREMIUMIZE, ALLDEBRID, EASYDEBRID, TORBOX)

# ── Debrid short codes (settings keys / cache keys) ───────────────────────────
RD = "rd"
PM = "pm"
AD = "ad"
ED = "ed"
TB = "tb"

# name → short code pairs used in enabled-debrid checks
PROVIDER_CODES = (
    (REAL_DEBRID, RD),
    (PREMIUMIZE,  PM),
    (ALLDEBRID,   AD),
    (EASYDEBRID,  ED),
    (TORBOX,      TB),
)

# ── Internal scraper / cloud IDs ──────────────────────────────────────────────
EASYNEWS = "easynews"
FOLDERS  = "folders"
EXTERNAL = "external"

RD_CLOUD  = "rd_cloud"
PM_CLOUD  = "pm_cloud"
AD_CLOUD  = "ad_cloud"
ED_CLOUD  = "ed_cloud"
TB_CLOUD  = "tb_cloud"

RD_BROWSE = "rd_browse"
PM_BROWSE = "pm_browse"
AD_BROWSE = "ad_browse"
ED_BROWSE = "ed_browse"
TB_BROWSE = "tb_browse"

DEFAULT_SCRAPERS = (EASYNEWS, RD_CLOUD, PM_CLOUD, AD_CLOUD, TB_CLOUD, FOLDERS)

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
    PREMIUMIZE:  ("apis.premiumize_api",  "PremiumizeAPI"),
    PM_CLOUD:    ("apis.premiumize_api",  "PremiumizeAPI"),
    PM_BROWSE:   ("apis.premiumize_api",  "PremiumizeAPI"),
    ALLDEBRID:   ("apis.alldebrid_api",   "AllDebridAPI"),
    AD_CLOUD:    ("apis.alldebrid_api",   "AllDebridAPI"),
    AD_BROWSE:   ("apis.alldebrid_api",   "AllDebridAPI"),
    EASYDEBRID:  ("apis.easydebrid_api",  "EasyDebridAPI"),
    ED_CLOUD:    ("apis.easydebrid_api",  "EasyDebridAPI"),
    ED_BROWSE:   ("apis.easydebrid_api",  "EasyDebridAPI"),
    TORBOX:      ("apis.torbox_api",      "TorBoxAPI"),
    TB_CLOUD:    ("apis.torbox_api",      "TorBoxAPI"),
    TB_BROWSE:   ("apis.torbox_api",      "TorBoxAPI"),
}

# ── Debrid icon names (used in downloader) ────────────────────────────────────
DEBRID_ICONS = {
    REAL_DEBRID: "realdebrid",
    PREMIUMIZE:  "premiumize",
    ALLDEBRID:   "alldebrid",
    EASYDEBRID:  "easydebrid",
    TORBOX:      "torbox",
}
