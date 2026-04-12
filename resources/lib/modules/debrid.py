# -*- coding: utf-8 -*-
from caches.debrid_cache import debrid_cache
from apis.real_debrid_api import RealDebridAPI
from apis.premiumize_api import PremiumizeAPI
from apis.alldebrid_api import AllDebridAPI
from apis.easydebrid_api import EasyDebridAPI
from apis.torbox_api import TorBoxAPI
from modules.providers import REAL_DEBRID, PREMIUMIZE, ALLDEBRID, EASYDEBRID, TORBOX, PROVIDER_CODES
from modules.source_utils import get_external_cache_status
from modules.kodi_utils import show_busy_dialog, hide_busy_dialog, notification, logger
from modules.settings import enabled_debrids_check

_DEBRID_CLASSES = {
	REAL_DEBRID: RealDebridAPI,
	PREMIUMIZE:  PremiumizeAPI,
	ALLDEBRID:   AllDebridAPI,
	EASYDEBRID:  EasyDebridAPI,
	TORBOX:      TorBoxAPI,
}

def debrid_enabled():
	return [name for name, code in PROVIDER_CODES if enabled_debrids_check(code)]

def debrid_for_ext_cache_check(enabled_debrid=None):
	if not enabled_debrid: enabled_debrid = debrid_enabled()
	return any(i in (REAL_DEBRID, ALLDEBRID) for i in enabled_debrid)

def manual_add_magnet_to_cloud(params):
	show_busy_dialog()
	function = _DEBRID_CLASSES[params['provider']]
	result = function().create_transfer(params['magnet_url'])
	function().clear_cache()
	hide_busy_dialog()
	if result == 'failed': notification('Failed')
	else: notification('Success')

def query_local_cache(hash_list):
	return debrid_cache.get_many(hash_list) or []

def add_to_local_cache(hash_list, debrid, expires=24):
	debrid_cache.set_many(hash_list, debrid, expires)

def cached_check(hash_list, cached_hashes, debrid):
	cached_list = [i[0] for i in cached_hashes if i[1] == debrid and i[2] == 'True']
	unchecked_list = [i for i in hash_list if not any([h for h in cached_hashes if h[0] == i and h[1] == debrid])]
	return cached_list, unchecked_list

def RD_check(hash_list, cached_hashes, data, active_debrid):
	expires = 24
	cached_hashes, unchecked_hashes = cached_check(hash_list, cached_hashes, 'rd')
	if unchecked_hashes:
		logger("Cache", f"RD: checking {len(unchecked_hashes)} hashes")
		results = get_external_cache_status('Real-Debrid', unchecked_hashes, data, active_debrid)
		if results:
			cached_append = cached_hashes.append
			process_list = []
			process_append = process_list.append
			try:
				for h in unchecked_hashes:
					cached = 'False'
					if h in results:
						cached_append(h)
						cached = 'True'
					process_append((h, cached))
			except Exception:
				for i in unchecked_hashes: process_append((i, 'False'))
		else: process_list, expires  = [(h, 'False') for h in unchecked_hashes], 2
		add_to_local_cache(process_list, 'rd', expires)
		logger("Cache", f"RD: {len(cached_hashes)} cached")
	return cached_hashes

def AD_check(hash_list, cached_hashes, data, active_debrid):
	expires = 24
	cached_hashes, unchecked_hashes = cached_check(hash_list, cached_hashes, 'ad')
	if unchecked_hashes:
		logger("Cache", f"AD: checking {len(unchecked_hashes)} hashes")
		results = get_external_cache_status('AllDebrid', unchecked_hashes, data, active_debrid)
		if results:
			cached_append = cached_hashes.append
			process_list = []
			process_append = process_list.append
			try:
				for h in unchecked_hashes:
					cached = 'False'
					if h in results:
						cached_append(h)
						cached = 'True'
					process_append((h, cached))
			except Exception:
				for i in unchecked_hashes: process_append((i, 'False'))
		else: process_list, expires  = [(h, 'False') for h in unchecked_hashes], 2
		add_to_local_cache(process_list, 'ad', expires)
		logger("Cache", f"AD: {len(cached_hashes)} cached")
	return cached_hashes

def PM_check(hash_list, cached_hashes):
	expires = 24
	cached_hashes, unchecked_hashes = cached_check(hash_list, cached_hashes, 'pm')
	if unchecked_hashes:
		logger("Cache", f"PM: checking {len(unchecked_hashes)} hashes")
		results = PremiumizeAPI().check_cache(unchecked_hashes)
		if results:
			cached_append = cached_hashes.append
			process_list = []
			process_append = process_list.append
			try:
				results = results['response']
				for c, h in enumerate(unchecked_hashes):
					cached = 'False'
					try:
						if results[c] is True:
							cached_append(h)
							cached = 'True'
					except Exception: pass
					process_append((h, cached))
			except Exception:
				for i in unchecked_hashes: process_append((i, 'False'))
		else: process_list, expires  = [(h, 'False') for h in unchecked_hashes], 2
		add_to_local_cache(process_list, 'pm', expires)
		logger("Cache", f"PM: {len(cached_hashes)} cached")
	return cached_hashes

def ED_check(hash_list, cached_hashes):
	expires = 24
	cached_hashes, unchecked_hashes = cached_check(hash_list, cached_hashes, 'ed')
	if unchecked_hashes:
		logger("Cache", f"ED: checking {len(unchecked_hashes)} hashes")
		results = EasyDebridAPI().check_cache(unchecked_hashes)
		if results:
			cached_append = cached_hashes.append
			process_list = []
			process_append = process_list.append
			try:
				results = results['cached']
				zipper = zip(unchecked_hashes, results)
				for h, is_cached in zipper:
					cached = 'False'
					if is_cached:
						cached_append(h)
						cached = 'True'
					process_append((h, cached))
			except Exception:
				for i in unchecked_hashes: process_append((i, 'False'))
		else: process_list, expires  = [(h, 'False') for h in unchecked_hashes], 2
		add_to_local_cache(process_list, 'ed', expires)
		logger("Cache", f"ED: {len(cached_hashes)} cached")
	return cached_hashes

def TB_check(hash_list, cached_hashes):
	expires = 24
	cached_hashes, unchecked_hashes = cached_check(hash_list, cached_hashes, 'tb')
	if unchecked_hashes:
		results = TorBoxAPI().check_cache(unchecked_hashes)
		if results:
			cached_append = cached_hashes.append
			process_list = []
			process_append = process_list.append
			try:
				data = results['data']
				results = [i['hash'] for i in data]
				for h in unchecked_hashes:
					cached = 'False'
					if h in results:
						cached_append(h)
						cached = 'True'
					process_append((h, cached))
			except:
				for i in unchecked_hashes: process_append((i, 'False'))
		else: process_list, expires  = [(h, 'False') for h in unchecked_hashes], 2
		add_to_local_cache(process_list, 'tb', expires)
	return cached_hashes
