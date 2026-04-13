# -*- coding: utf-8 -*-
from caches.debrid_cache import debrid_cache
from apis.real_debrid_api import RealDebridAPI
from modules.providers import REAL_DEBRID, PROVIDER_CODES
from modules.source_utils import get_external_cache_status
from modules.kodi_utils import show_busy_dialog, hide_busy_dialog, notification, logger
from modules.settings import enabled_debrids_check

_DEBRID_CLASSES = {
    REAL_DEBRID: RealDebridAPI,
}


def debrid_enabled():
    return [name for name, code in PROVIDER_CODES if enabled_debrids_check(code)]


def debrid_for_ext_cache_check(enabled_debrid=None):
    if not enabled_debrid:
        enabled_debrid = debrid_enabled()
    return any(i in (REAL_DEBRID) for i in enabled_debrid)


def manual_add_magnet_to_cloud(params):
    show_busy_dialog()
    function = _DEBRID_CLASSES[params["provider"]]
    result = function().create_transfer(params["magnet_url"])
    function().clear_cache()
    hide_busy_dialog()
    if result == "failed":
        notification("Failed")
    else:
        notification("Success")


def query_local_cache(hash_list):
    return debrid_cache.get_many(hash_list) or []


def add_to_local_cache(hash_list, debrid, expires=24):
    debrid_cache.set_many(hash_list, debrid, expires)


def cached_check(hash_list, cached_hashes, debrid):
    cached_list = [i[0] for i in cached_hashes if i[1] == debrid and i[2] == "True"]
    unchecked_list = [
        i
        for i in hash_list
        if not any([h for h in cached_hashes if h[0] == i and h[1] == debrid])
    ]
    return cached_list, unchecked_list


def RD_check(hash_list, cached_hashes, data, active_debrid):
    expires = 24
    cached_hashes, unchecked_hashes = cached_check(hash_list, cached_hashes, "rd")
    if unchecked_hashes:
        logger("Cache", f"RD: checking {len(unchecked_hashes)} hashes")
        results = get_external_cache_status(
            "Real-Debrid", unchecked_hashes, data, active_debrid
        )
        if results:
            cached_append = cached_hashes.append
            process_list = []
            process_append = process_list.append
            try:
                for h in unchecked_hashes:
                    cached = "False"
                    if h in results:
                        cached_append(h)
                        cached = "True"
                    process_append((h, cached))
            except Exception:
                for i in unchecked_hashes:
                    process_append((i, "False"))
        else:
            process_list, expires = [(h, "False") for h in unchecked_hashes], 2
        add_to_local_cache(process_list, "rd", expires)
        logger("Cache", f"RD: {len(cached_hashes)} cached")
    return cached_hashes
