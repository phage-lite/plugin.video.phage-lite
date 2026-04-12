# -*- coding: utf-8 -*-
import re
import json
import time
import requests
from threading import Thread
from urllib.parse import urlencode
from caches.main_cache import cache_object
from modules.settings_manager import get_setting, set_setting
from modules.utils import copy2clip, make_qrcode
from modules.source_utils import supported_video_extensions, seas_ep_filter, extras
from modules.kodi_utils import sleep, ok_dialog, progress_dialog, notification

class PremiumizeAPI:
	def __init__(self):
		self.token = get_setting('pm.token')

	def auth(self):
		self.token = ''
		line = '%s[CR]%s[CR]%s'
		data = {'response_type': 'device_code', 'client_id': '888228107'}
		url = 'https://www.premiumize.me/token'
		response = self._post(url, data)
		user_code = response['user_code']
		auth_url = response.get('verification_uri')
		qr_code = make_qrcode(auth_url) or ''
		copy2clip(auth_url)
		content = 'Authorize Debrid Services[CR]Navigate to: [B]%s[/B][CR]Enter the following code: [B]%s[/B]' % (auth_url, user_code)
		progressDialog = progress_dialog('Premiumize Authorize', qr_code)
		progressDialog.update(content, 0)
		device_code = response['device_code']
		expires_in = int(response['expires_in'])
		sleep_interval = int(response['interval'])
		poll_url = 'https://www.premiumize.me/token'
		data = {'grant_type': 'device_code', 'client_id': '888228107', 'code': device_code}
		start, time_passed = time.time(), 0
		while not progressDialog.iscanceled() and time_passed < expires_in and not self.token:
			sleep(1000 * sleep_interval)
			response = self._post(poll_url, data)
			if 'error' in response:
				time_passed = time.time() - start
				progress = int(100 * time_passed/float(expires_in))
				progressDialog.update(content, progress)
				continue
			try:
				progressDialog.close()
				self.token = str(response['access_token'])
				set_setting('pm.token', self.token)
			except:
				ok_dialog(text='Error')
				break
		try: progressDialog.close()
		except: pass
		if self.token:
			account_info = self.account_info()
			set_setting('pm.account_id', str(account_info['customer_id']))
			set_setting('pm.enabled', 'true')
			ok_dialog(text='Success')

	def revoke(self):
		set_setting('pm.token', '')
		set_setting('pm.account_id', '')
		set_setting('pm.enabled', 'false')
		notification('Premiumize Authorization Reset', 3000)

	def account_info(self):
		return self._post('account/info')

	def check_cache(self, hashes):
		return self._post('cache/check', {'items[]': hashes})

	def check_single_magnet(self, hash_string):
		return self.check_cache(hash_string)['response'][0]

	def unrestrict_link(self, link):
		response = self._post('transfer/directdl', {'src': link})
		try: return self.add_headers_to_url(response['content'][0]['link'])
		except: return None

	def resolve_magnet(self, magnet_url, info_hash, store_to_cloud, title, season, episode):
		try:
			file_url = None
			correct_files = []
			append = correct_files.append
			extensions = supported_video_extensions()
			result = self.instant_transfer(magnet_url)
			if not 'status' in result or result['status'] != 'success': return None
			content = result.get('content')
			valid_results = [i for i in content if any(i.get('path').lower().endswith(x) for x in extensions) and not i.get('link', '') == '']
			if len(valid_results) == 0: return
			if season:
				extras_filter = extras()
				episode_title = re.sub(r'[^A-Za-z0-9-]+', '.', title.replace('\'', '').replace('&', 'and').replace('%', '.percent')).lower()
				for item in valid_results:
					if seas_ep_filter(season, episode, item['path'].split('/')[-1]): append(item)
					if len(correct_files) == 0: continue
					for i in correct_files:
						compare_link = seas_ep_filter(season, episode, i['path'], split=True)
						compare_link = re.sub(episode_title, '', compare_link)
						if not any(x in compare_link for x in extras_filter):
							file_url = i['link']
							break
			else:
				file_url = max(valid_results, key=lambda x: int(x.get('size'))).get('link', None)
				if not any(file_url.lower().endswith(x) for x in extensions): file_url = None
			if file_url:
				if store_to_cloud: Thread(target=self.create_transfer, args=(magnet_url,)).start()
				return self.add_headers_to_url(file_url)
		except: return None

	def display_magnet_pack(self, magnet_url, info_hash):
		try:
			end_results = []
			append = end_results.append
			extensions = supported_video_extensions()
			result = self.instant_transfer(magnet_url)
			if not 'status' in result or result['status'] != 'success': return None
			for item in result.get('content'):
				if any(item.get('path').lower().endswith(x) for x in extensions) and not item.get('link', '') == '':
					try: path = item['path'].split('/')[-1]
					except: path = item['path']
					append({'link': item['link'], 'filename': path, 'size': item['size']})
			return end_results
		except: return None

	def user_cloud(self, folder_id=None):
		if folder_id:
			string = 'pm_user_cloud_%s' % folder_id
			url = 'folder/list?id=%s' % folder_id
		else:
			string = 'pm_user_cloud_root'
			url = 'folder/list'
		return cache_object(self._get, string, url, False, 0.03)

	def user_cloud_all(self):
		return cache_object(self._get, 'pm_user_cloud_all_files', 'item/listall', False, 0.03)

	def rename_cache_item(self, file_type, file_id, new_name):
		url = 'folder/rename' if file_type == 'folder' else 'item/rename'
		response = self._post(url, {'id': file_id, 'name': new_name})
		return response['status']

	def transfers_list(self):
		return self._get('transfer/list')

	def instant_transfer(self, magnet_url):
		return self._post('transfer/directdl', {'src': magnet_url})

	def create_transfer(self, magnet):
		return self._post('transfer/create', {'src': magnet, 'folder_id': 0})

	def delete_transfer(self, transfer_id):
		return self._post('transfer/delete', {'id': transfer_id})

	def delete_object(self, object_type, object_id):
		response = self._post('%s/delete' % object_type, {'id': object_id})
		return response['status']

	def get_item_details(self, item_id):
		return cache_object(self._post, 'pm_item_details_%s' % item_id, ['item/details', {'id': item_id}], False, 0.5)

	def add_headers_to_url(self, url):
		return url + '|' + urlencode(self.headers())

	def headers(self):
		return {'User-Agent': 'Bacterio for Kodi', 'Authorization': 'Bearer %s' % self.token}

	def _get(self, url, data=None):
		if not self.token: return None
		if data is None: data = {}
		url = 'https://www.premiumize.me/api/' + url
		response = requests.get(url, data=data, headers=self.headers(), timeout=20).text
		try: return json.loads(response)
		except Exception: return response

	def _post(self, url, data=None):
		if not self.token and 'token' not in url: return None
		if data is None: data = {}
		if 'token' not in url: url = 'https://www.premiumize.me/api/' + url
		response = requests.post(url, data=data, headers=self.headers(), timeout=20).text
		try: return json.loads(response)
		except: return response

	def clear_cache(self, clear_hashes=True):
		try:
			from caches.debrid_cache import debrid_cache
			from caches.base_cache import connect_database
			dbcon = connect_database('maincache_db')
			try:
				user_cloud_cache = dbcon.execute("SELECT id FROM maincache WHERE id LIKE ?", ('pm_user_cloud%',)).fetchall()
				for i in [r[0] for r in user_cloud_cache]:
					dbcon.execute("DELETE FROM maincache WHERE id=?", (i,))
				user_cloud_success = True
			except: user_cloud_success = False
			try:
				dbcon.execute("DELETE FROM maincache WHERE id=?", ('pm_transfers_list',))
				download_links_success = True
			except: download_links_success = False
			if clear_hashes:
				try:
					debrid_cache.clear_debrid_results('pm')
					hash_cache_status_success = True
				except: hash_cache_status_success = False
			else: hash_cache_status_success = True
		except: return False
		return False not in (user_cloud_success, download_links_success, hash_cache_status_success)

Premiumize = PremiumizeAPI()
