# -*- coding: utf-8 -*-
import json
import requests
from urllib.parse import urlencode
from modules.settings_manager import get_setting, set_setting
from modules.kodi_utils import make_session, kodi_dialog, notification, ok_dialog, confirm_dialog
from modules.source_utils import supported_video_extensions, seas_ep_filter, extras

session = make_session('https://easydebrid.com/api/v1/')

class EasyDebridAPI:
	def __init__(self):
		self.token = get_setting('ed.token')
		self.base_url = 'https://easydebrid.com/api/v1/'

	def _get(self, url, data=None):
		if not self.token: return None
		if data is None: data = {}
		response = session.get(self.base_url + url, data=data, headers=self.headers(), timeout=20)
		return response.json()

	def _post(self, url, params=None, json=None, data=None):
		if not self.token: return None
		response = session.post(self.base_url + url, params=params, json=json, data=data, headers=self.headers(), timeout=20)
		return response.json()

	def account_info(self):
		return self._get('user/details')

	def add_magnet(self, magnet):
		return self._post('link/generate', json={'url': magnet})

	def check_cache_single(self, _hash):
		return self._post('link/lookup', json={'urls': [_hash]})

	def check_cache(self, hashlist):
		return self._post('link/lookup', json={'urls': hashlist})

	def create_transfer(self, magnet_url):
		result = self.add_magnet(magnet_url)
		if 'files' not in result: return ''
		return result.get('files', '')

	def resolve_magnet(self, magnet_url, info_hash, store_to_cloud, title, season, episode):
		try:
			file_url = None
			extensions = supported_video_extensions()
			torrent = self.add_magnet(magnet_url)
			torrent_files = [item for item in torrent['files'] if item['filename'].lower().endswith(tuple(extensions))]
			if not torrent_files: return None
			if season:
				torrent_files = [i for i in torrent_files if seas_ep_filter(season, episode, i['filename'])]
				if not torrent_files: return None
			else:
				if self._m2ts_check(torrent_files): return None
				extras_filter = extras()
				torrent_files = [i for i in torrent_files if not any(x in i['filename'] for x in extras_filter)]
				torrent_files.sort(key=lambda k: k['size'], reverse=True)
			file_url = torrent_files[0]['url']
			return self.add_headers_to_url(file_url)
		except: return None

	def display_magnet_pack(self, magnet_url, info_hash):
		try:
			extensions = supported_video_extensions()
			torrent = self.add_magnet(magnet_url)
			files = torrent['files']
			return [{'link': item['url'], 'filename': item['filename'], 'size': item['size']}
					for item in files if item['filename'].lower().endswith(tuple(extensions))] or None
		except: return None

	def add_headers_to_url(self, url):
		return url + '|' + urlencode(self.headers())

	def headers(self):
		return {'User-Agent': 'Bacterio for Kodi', 'Authorization': 'Bearer %s' % self.token}

	def _m2ts_check(self, folder_items):
		return any(item['filename'].endswith('.m2ts') for item in folder_items)

	def auth(self):
		api_key = kodi_dialog().input('EasyDebrid API Key:')
		if not api_key: return
		self.token = api_key
		response = self.account_info()
		try:
			response['id']
			set_setting('ed.token', api_key)
			set_setting('ed.enabled', 'true')
			message = 'Success'
		except: message = 'Failed'
		ok_dialog(text=message)

	def revoke(self):
		if not confirm_dialog(): return
		set_setting('ed.token', '')
		set_setting('ed.enabled', 'false')
		notification('Easy Debrid Authorization Reset', 3000)

	def clear_cache(self, clear_hashes=True):
		try:
			from caches.debrid_cache import debrid_cache
			from caches.base_cache import connect_database
			dbcon = connect_database('maincache_db')
			try:
				dbcon.execute("DELETE FROM maincache WHERE id=?", ('ed_user_cloud',))
				dbcon.execute("DELETE FROM maincache WHERE id LIKE ?", ('ed_user_cloud%',))
				user_cloud_success = True
			except: user_cloud_success = False
			if clear_hashes:
				try:
					debrid_cache.clear_debrid_results('ed')
					hash_cache_status_success = True
				except: hash_cache_status_success = False
			else: hash_cache_status_success = True
		except: return False
		return False not in (user_cloud_success, hash_cache_status_success)

EasyDebrid = EasyDebridAPI()
