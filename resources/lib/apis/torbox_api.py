# -*- coding: utf-8 -*-
from threading import Thread
from urllib.parse import urlencode
from caches.main_cache import cache_object
from modules.settings_manager import get_setting, set_setting
from modules.source_utils import supported_video_extensions, seas_ep_filter, extras
from modules.kodi_utils import make_session, kodi_dialog, ok_dialog, notification, confirm_dialog

session = make_session('https://api.torbox.app/v1/api/')

class TorBoxAPI:
	def __init__(self):
		self.token = get_setting('tb.token')

	def _get(self, url, data=None):
		if not self.token: return None
		if data is None: data = {}
		headers = {'Authorization': 'Bearer %s' % self.token}
		url = 'https://api.torbox.app/v1/api/' + url
		response = session.get(url, params=data, headers=headers, timeout=20)
		return response.json()

	def _post(self, url, params=None, json=None, data=None):
		if not self.token: return None
		headers = {'Authorization': 'Bearer %s' % self.token}
		url = 'https://api.torbox.app/v1/api/' + url
		response = session.post(url, params=params, json=json, data=data, headers=headers, timeout=20)
		return response.json()

	def add_headers_to_url(self, url):
		return url + '|' + urlencode({'User-Agent': 'Mozilla/5.0'})

	def account_info(self):
		return self._get('user/me')

	def user_cloud(self):
		return cache_object(self._get, 'tb_user_cloud', 'torrents/mylist', False, 0.03)

	def user_cloud_usenet(self):
		return cache_object(self._get, 'tb_user_cloud_usenet', 'usenet/mylist', False, 0.03)

	def user_cloud_info(self, request_id=''):
		return cache_object(self._get, 'tb_user_cloud_%s' % request_id, 'torrents/mylist?id=%s' % request_id, False, 0.03)

	def user_cloud_info_usenet(self, request_id=''):
		return cache_object(self._get, 'tb_user_cloud_usenet_%s' % request_id, 'usenet/mylist?id=%s' % request_id, False, 0.03)

	def user_cloud_clear(self):
		if not confirm_dialog(): return
		data = {'all': True, 'operation': 'delete'}
		self._post('torrents/controltorrent', json=data)
		self._post('usenet/controlusenetdownload', json=data)
		self.clear_cache()

	def torrent_info(self, request_id=''):
		return self._get('torrents/mylist?id=%s' % request_id)

	def delete_torrent(self, request_id=''):
		return self._post('torrents/controltorrent', json={'torrent_id': request_id, 'operation': 'delete'})

	def delete_usenet(self, request_id=''):
		return self._post('usenet/controlusenetdownload', json={'usenet_id': request_id, 'operation': 'delete'})

	def unrestrict_link(self, file_id):
		torrent_id, file_id = file_id.split(',')
		data = {'token': self.token, 'torrent_id': torrent_id, 'file_id': file_id}
		try: return self._get('torrents/requestdl', data=data)['data']
		except: return None

	def unrestrict_usenet(self, file_id):
		usenet_id, file_id = file_id.split(',')
		params = {'token': self.token, 'usenet_id': usenet_id, 'file_id': file_id, 'user_ip': True}
		try: return self._get('usenet/requestdl', params=params)['data']
		except: return None

	def add_magnet(self, magnet):
		return self._post('torrents/createtorrent', data={'magnet': magnet, 'seed': 3, 'allow_zip': False})

	def check_cache_single(self, _hash):
		return self._get('torrents/checkcached', data={'hash': _hash, 'format': 'list'})

	def check_cache(self, hashlist):
		return self._post('torrents/checkcached', params={'format': 'list'}, json={'hashes': hashlist})

	def create_transfer(self, magnet_url):
		result = self.add_magnet(magnet_url)
		if not result['success']: return ''
		return result['data'].get('torrent_id', '')

	def resolve_magnet(self, magnet_url, info_hash, store_to_cloud, title, season, episode):
		try:
			file_url, torrent_id = None, None
			extensions = supported_video_extensions()
			extras_filter = extras()
			extras_filtering_list = tuple(i for i in extras_filter if not i in title.lower())
			torrent = self.add_magnet(magnet_url)
			if not torrent['success']: return None
			torrent_id = torrent['data']['torrent_id']
			torrent_files = self.torrent_info(torrent_id)
			files = torrent_files['data']['files']
			selected_files = [{'url': '%d,%d' % (torrent_id, item['id']), 'filename': item['short_name'], 'size': item['size']}
							for item in files if item['short_name'].lower().endswith(tuple(extensions))]
			if not selected_files: return None
			if season:
				selected_files = [i for i in selected_files if seas_ep_filter(season, episode, i['filename'])]
			else:
				if self._m2ts_check(selected_files): return None
				selected_files = [i for i in selected_files if not any(x in i['filename'] for x in extras_filtering_list)]
				selected_files.sort(key=lambda k: k['size'], reverse=True)
			if not selected_files: return None
			file_url = self.unrestrict_link(selected_files[0]['url'])
			if not store_to_cloud: Thread(target=self.delete_torrent, args=(torrent_id,)).start()
			return file_url
		except:
			if torrent_id: self.delete_torrent(torrent_id)
			return None

	def display_magnet_pack(self, magnet_url, info_hash):
		torrent_id = None
		try:
			extensions = supported_video_extensions()
			torrent = self.add_magnet(magnet_url)
			if not torrent['success']: return None
			torrent_id = torrent['data']['torrent_id']
			files = self.torrent_info(torrent_id)['data']['files']
			torrent_files = [{'link': '%d,%d' % (torrent_id, item['id']), 'filename': item['short_name'], 'size': item['size']}
							for item in files if item['short_name'].lower().endswith(tuple(extensions))]
			Thread(target=self.delete_torrent, args=(torrent_id,)).start()
			return torrent_files or None
		except:
			if torrent_id: self.delete_torrent(torrent_id)
			return None

	def _m2ts_check(self, folder_items):
		return any(item['filename'].endswith('.m2ts') for item in folder_items)

	def auth(self):
		api_key = kodi_dialog().input('TorBox API Key:')
		if not api_key: return
		try:
			self.token = api_key
			r = self.account_info()
			r['data']['customer']
			set_setting('tb.token', api_key)
			set_setting('tb.enabled', 'true')
			message = 'Success'
		except: message = 'An Error Occurred'
		ok_dialog(text=message)

	def revoke(self):
		if not confirm_dialog(): return
		set_setting('tb.token', '')
		set_setting('tb.enabled', 'false')
		notification('TorBox Authorization Reset', 3000)

	def clear_cache(self, clear_hashes=True):
		try:
			from caches.debrid_cache import debrid_cache
			from caches.base_cache import connect_database
			dbcon = connect_database('maincache_db')
			try:
				dbcon.execute("DELETE FROM maincache WHERE id=?", ('tb_user_cloud',))
				dbcon.execute("DELETE FROM maincache WHERE id LIKE ?", ('tb_user_cloud%',))
				user_cloud_success = True
			except: user_cloud_success = False
			if clear_hashes:
				try:
					debrid_cache.clear_debrid_results('tb')
					hash_cache_status_success = True
				except: hash_cache_status_success = False
			else: hash_cache_status_success = True
		except: return False
		return False not in (user_cloud_success, hash_cache_status_success)

TorBox = TorBoxAPI()
