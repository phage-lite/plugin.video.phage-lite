import re
import time
from typing import Any
import requests
from threading import Thread
from caches.main_cache import cache_object
from modules.settings_manager import get_setting, set_setting
from modules.utils import make_tinyurl, unwrap
from modules.kodi_ops import make_qrcode
from modules.source_utils import supported_video_extensions, seas_ep_filter, extras
from modules.kodi_utils import sleep, ok_dialog, progress_dialog, notification
from modules.logger import log
from apis import services
from data.setting_ids import SettingID as SID


class RealDebridAPI:
    def __init__(self):
        self.client_id: str = "X245A4XAIBGVM"
        self.auth_url: str = "https://api.real-debrid.com/oauth/v2"
        self.access_token: str = get_setting(SID.RD_ACCESS_TOKEN)
        self.client_secret: str = get_setting(SID.RD_CLIENT_SECRET)
        self.refresh_token: str = get_setting(SID.RD_REFRESH_TOKEN)
        self.refresh_retries: int = 0
        self.break_auth_loop: bool = False

    def auth(self):
        url = f"{self.auth_url}/device/code?client_id={self.client_id}&new_credentials=yes"
        response = requests.get(url, timeout=20).json()
        user_code = response["user_code"]
        auth_url = response["direct_verification_url"]
        qr_code = make_qrcode(auth_url) or ""
        short_url = make_tinyurl(auth_url)
        if short_url:
            p_dialog_insert = f"OR visit this URL: [B]{short_url}[/B][CR]OR Enter this Code: [B]{user_code}[/B]"
        else:
            p_dialog_insert = f"OR Enter this Code: [B]{user_code}[/B]"
        content = f"Please Scan the QR Code{p_dialog_insert}[CR]"
        progressDialog = unwrap(
            progress_dialog("Real Debrid Authorize", qr_code), "progress_dialog"
        )
        progressDialog.update(content, 0)
        expires_in = int(response["expires_in"])
        sleep_interval = int(response["interval"])
        device_code = response["device_code"]
        poll_url = f"{self.auth_url}/device/credentials?client_id={self.client_id}&code={device_code}"
        start, time_passed = time.time(), 0
        while (
            not progressDialog.iscanceled()
            and time_passed < expires_in
            and not self.client_secret
        ):
            sleep(1000 * sleep_interval)
            try:
                response = requests.get(poll_url, timeout=20).json()
            except Exception:
                continue
            if "error" in response:
                time_passed = time.time() - start
                progress = int(100 * time_passed / float(expires_in))
                progressDialog.update(content, progress)
                continue
            try:
                self.client_secret = response["client_secret"]
                self.client_id = response["client_id"]
                progressDialog.close()
            except Exception:
                _ = ok_dialog(text="Error")
                break
        try:
            progressDialog.close()
        except Exception:
            pass
        if self.client_secret:
            data = {
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "code": device_code,
                "grant_type": "http://oauth.net/grant_type/device/1.0",
            }
            url = f"{self.auth_url}/token"
            try:
                response = requests.post(url, data=data, timeout=20).json()
                log(str(response))
                self.access_token = response["access_token"]
                self.refresh_token = response["refresh_token"]
                set_setting(SID.RD_ACCESS_TOKEN, self.access_token)
                set_setting(SID.RD_REFRESH_TOKEN, self.refresh_token)
                set_setting(SID.RD_CLIENT_SECRET, self.client_secret)
                set_setting(SID.RD_CLIENT_ID, self.client_id)
                _ = ok_dialog(text="Success")
            except Exception as e:
                _ = ok_dialog(text="Error")
                log(str(e))


    def get_refresh_token(self):
        try:
            url = f"{self.auth_url}/token"
            data = {
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "code": self.refresh_token,
                "grant_type": "http://oauth.net/grant_type/device/1.0",
            }

            response = requests.post(url, data=data, timeout=20).json()
            self.access_token = response["access_token"]
            self.refresh_token = response["refresh_token"]
            set_setting(SID.RD_ACCESS_TOKEN, self.access_token)
            set_setting(SID.RD_REFRESH_TOKEN, self.refresh_token)
            return True
        except Exception as e:
            log(str(e), "refresh_token")
            return False

    def revoke(self):
        set_setting(SID.RD_CLIENT_ID, "")
        set_setting(SID.RD_CLIENT_SECRET, "")
        set_setting(SID.RD_REFRESH_TOKEN, "")
        set_setting(SID.RD_ACCESS_TOKEN, "")
        set_setting(SID.RD_ACCOUNT_ID, "")
        notification("Real Debrid Authorization Reset", 3000)

    def account_info(self):
        url = "user"
        return self._get(url)

    def check_cache(self, hashes: list[str]):
        hash_string = "/".join(hashes)
        url = f"torrents/instantAvailability/{hash_string}"
        return self._get(url)

    def check_hash(self, hash_string: str):
        url = f"torrents/instantAvailability/{hash_string}"
        return self._get(url)

    def check_single_magnet(self, hash_string: str):
        cache_info = self.check_hash(hash_string)
        cached = False
        if cache_info is not None:
            if hash_string in cache_info:
                info = cache_info[hash_string]
                if isinstance(info, dict) and len(info.get(key="rd")) > 0:  # pyright: ignore[reportUnknownMemberType, reportCallIssue, reportUnknownArgumentType]
                    cached = True
        return cached

    def torrents_activeCount(self):
        url = "torrents/activeCount"
        return self._get(url)

    def user_cloud(self):
        string = "rd_user_cloud"
        url = "torrents?limit=500"
        return cache_object(self._get, string, url, False, 0.03)

    def user_cloud_check(self):
        url = "torrents?limit=500"
        return self._get(url)

    def downloads(self):
        string = "rd_downloads"
        url = "downloads?limit=500"
        return cache_object(self._get, string, url, False, 0.03)

    def user_cloud_info(self, file_id: str):
        string = "rd_user_cloud_info_%s" % file_id
        url = "torrents/info/%s" % file_id
        return cache_object(self._get, string, url, False, 0.03)

    def user_cloud_info_check(self, file_id: str):
        url = "torrents/info/%s" % file_id
        return self._get(url)

    def torrent_info(self, file_id: str):
        url = "torrents/info/%s" % file_id
        return self._get(url)

    def unrestrict_link(self, link: str):
        url = "unrestrict/link"
        post_data = {"link": link}
        response = self._post(url, post_data)
        try:
            return response["download"]
        except Exception:
            return None

    def add_magnet(self, magnet: str):
        post_data = {"magnet": magnet}
        url = "torrents/addMagnet"
        result = self._post(url, post_data)
        log(f"result {result}", "RealDebridAPI")
        return result

    def create_transfer(self, magnet_url: str):
        try:
            extensions = supported_video_extensions()
            torrent = self.add_magnet(magnet_url)
            torrent_id = torrent["id"]
            info = self.torrent_info(torrent_id)
            files = info["files"]
            self.add_torrent_select(torrent_id, "all")
            return "success"
        except Exception:
            self.delete_torrent(torrent_id)
            return "failed"

    def add_torrent_select(self, torrent_id: str, file_ids: str):
        _ = self.clear_cache(clear_hashes=False)
        url = "torrents/selectFiles/%s" % torrent_id
        post_data = {"files": file_ids}
        return self._post(url, post_data)

    def delete_torrent(self, folder_id: str):
        return self._call("delete", "torrents/delete/%s" % folder_id)

    def delete_download(self, download_id: str):
        return self._call("delete", "downloads/delete/%s" % download_id)

    def resolve_magnet(
        self,
        magnet_url: str,
        info_hash: str,
        store_to_cloud: bool,
        title: str,
        season: int,
        episode: int,
    ):
        compare_title = re.sub(
            r"[^A-Za-z0-9]+",
            ".",
            title.replace("'", "").replace("&", "and").replace("%", ".percent"),
        ).lower()
        attempts, transfer_finished = 0, False
        extensions = supported_video_extensions()
        torrent_id = None
        try:
            torrent = self.add_magnet(magnet_url)
            if torrent is None or "error" in torrent:
                log(f"Couldn't add magnet {magnet_url}", "RealDebridAPI")
                return None
            torrent_id = torrent["id"]
            _ = self.add_torrent_select(torrent_id, "all")
            sleep(1000)
            torrent_info = self.user_cloud_info_check(torrent_id)
            if (
                torrent_info is None
                or not torrent_info["links"]
                or "error" in torrent_info
            ):
                log(f"Couldn't get torrent info {torrent_id}", "RealDebridAPI")
                _ = self.delete_torrent(torrent_id)
                return None
            sleep(1000)
            while attempts <= 4 and not transfer_finished:
                active_count = unwrap(self.torrents_activeCount())
                active_list = active_count["list"]
                attempts += 1
                if info_hash in active_list:
                    sleep(1000)
                else:
                    transfer_finished = True
            if not transfer_finished:
                _ = self.delete_torrent(torrent_id)
                return None
            files = [
                i
                for i in torrent_info["files"]
                if i["selected"] == 1 and i["path"].lower().endswith(tuple(extensions))
            ]
            selected_files = [(idx, i) for idx, i in enumerate(files)]
            selected_files = sorted(
                selected_files, key=lambda x: x[1]["bytes"], reverse=True
            )
            match = False
            if season:
                correct_files: list[Any] = []
                correct_file_check = False
                for value in selected_files:
                    correct_file_check = seas_ep_filter(
                        season, episode, value[1]["path"]
                    )
                    if correct_file_check:
                        correct_files.append(value[1])
                        break
                if len(correct_files) == 0:
                    match = False
                else:
                    for i in correct_files:
                        compare_link = seas_ep_filter(
                            season, episode, i["path"], split=True
                        )
                        compare_link = re.sub(compare_title, "", compare_link)
                        extras_filter = extras()
                        if any(x in compare_link for x in extras_filter):
                            continue
                        else:
                            match = True
                            break
                if match:
                    index = [
                        i[0]
                        for i in selected_files
                        if i[1]["path"] == correct_files[0]["path"]
                    ][0]
            else:
                if self._m2ts_check(selected_files):
                    self.delete_torrent(torrent_id)
                    return None
                for value in selected_files:
                    filename = re.sub(
                        r"[^A-Za-z0-9-]+",
                        ".",
                        value[1]["path"]
                        .rsplit("/", 1)[1]
                        .replace("'", "")
                        .replace("&", "and")
                        .replace("%", ".percent"),
                    ).lower()
                    filename_info = filename.replace(compare_title, "")
                    extras_filter = extras()
                    if any(x in filename_info for x in extras_filter):
                        continue
                    match, index = True, value[0]
                    break
            if match:
                rd_link = torrent_info["links"][index]
                file_url = unwrap(self.unrestrict_link(rd_link), "file_url")
                if file_url.endswith("rar") or not any(
                    file_url.lower().endswith(x) for x in extensions
                ):
                    file_url = None
                if not store_to_cloud:
                    Thread(target=self.delete_torrent, args=(torrent_id,)).start()
                return file_url
            else:
                self.delete_torrent(torrent_id)
        except Exception:
            if torrent_id:
                self.delete_torrent(torrent_id)
            return None

    def display_magnet_pack(self, magnet_url, info_hash):
        try:
            torrent_id = None
            torrent = unwrap(self.add_magnet(magnet_url), "torrent")
            torrent_id = torrent["id"]
            self.add_torrent_select(torrent_id, "all")
            sleep(1000)
            torrent_info = unwrap(
                self.user_cloud_info_check(torrent_id), "torrent_info"
            )
            if not torrent_info["links"] or "error" in torrent_info:
                self.delete_torrent(torrent_id)
                return None
            sleep(1000)
            attempts, transfer_finished = 0, False
            while attempts <= 4 and not transfer_finished:
                active_count = self.torrents_activeCount()
                active_list = active_count["list"]
                attempts += 1
                if info_hash in active_list:
                    sleep(1000)
                else:
                    transfer_finished = True
            if not transfer_finished:
                self.delete_torrent(torrent_id)
                return None
            files = [i for i in torrent_info["files"] if i["selected"] == 1]
            list_file_items = [
                dict(i, **{"link": torrent_info["links"][idx]})
                for idx, i in enumerate(files)
            ]
            list_file_items = [
                {
                    "link": i["link"],
                    "filename": i["path"].replace("/", ""),
                    "size": i["bytes"],
                }
                for i in list_file_items
            ]
            self.delete_torrent(torrent_id)
            return list_file_items
        except Exception:
            if torrent_id:
                self.delete_torrent(torrent_id)
            return None

    def video_only(self, storage_variant, extensions):
        values = storage_variant.values()
        return (
            False
            if len(
                [
                    i
                    for i in values
                    if not i["filename"].lower().endswith(tuple(extensions))
                ]
            )
            > 0
            else True
        )

    def name_check(self, storage_variant, season, episode, seas_ep_filter):
        values = storage_variant.values()
        return (
            len([i for i in values if seas_ep_filter(season, episode, i["filename"])])
            > 0
        )

    def sort_cache_list(self, unsorted_list):
        sorted_list = sorted(unsorted_list, key=lambda x: x[1], reverse=True)
        return [i[0] for i in sorted_list]

    def _m2ts_check(self, folder_details):
        for item in folder_details:
            if item["path"].endswith(".m2ts"):
                return True
        return False

    def _call(self, method: str, endpoint: str, **kwargs: Any):
        """Call services, retry once after token refresh on bad_token response."""
        resp = getattr(services, method)("real_debrid", endpoint, raw=True, **kwargs)
        log(f"raw resp {str(resp)}", "RealDebridAPI")
        if resp is None:
            return None
        if any(v in resp.text for v in ("bad_token", "Bad Request")):
            if self.get_refresh_token():
                resp = getattr(services, method)(
                    "real_debrid", endpoint, raw=True, **kwargs
                )
            else:
                return None
        try:
            return resp.json()
        except Exception:
            return resp

    def _get(self, url: str):
        return self._call("get", url)

    def _post(self, url, post_data):
        return self._call("post", url, form=True, data=post_data)

    def clear_cache(self, clear_hashes=True):
        try:
            from caches.debrid_cache import debrid_cache
            from caches.base_cache import connect_database

            dbcon = connect_database("maincache_db")
            user_cloud_success = False
            # USER CLOUD
            try:
                try:
                    cache = dbcon.execute(
                        """SELECT data FROM maincache WHERE id LIKE ?""",
                        ("rd_user_cloud_info_%",),
                    ).fetchall()
                    user_cloud_info_caches = [eval(i[0])["id"] for i in cache]
                except Exception:
                    user_cloud_success = True
                if not user_cloud_success:
                    dbcon.execute(
                        """DELETE FROM maincache WHERE id=?""", ("rd_user_cloud",)
                    )
                    for i in user_cloud_info_caches:
                        dbcon.execute(
                            """DELETE FROM maincache WHERE id=?""",
                            ("rd_user_cloud_info_%s" % i,),
                        )
                    user_cloud_success = True
            except Exception:
                user_cloud_success = False
            # DOWNLOAD LINKS
            try:
                dbcon.execute("""DELETE FROM maincache WHERE id=?""", ("rd_downloads",))
                download_links_success = True
            except Exception:
                download_links_success = False
            # HASH CACHED STATUS
            if clear_hashes:
                try:
                    debrid_cache.clear_debrid_results("rd")
                    hash_cache_status_success = True
                except Exception:
                    hash_cache_status_success = False
            else:
                hash_cache_status_success = True
        except Exception:
            return False
        if False in (
            user_cloud_success,
            download_links_success,
            hash_cache_status_success,
        ):
            return False
        return True


RealDebrid = RealDebridAPI()
