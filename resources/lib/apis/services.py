# -*- coding: utf-8 -*-
"""
services.py — central HTTP machinery for all external API calls.

Each entry in SERVICES defines how to reach a service and how to authenticate.
The api files (trakt_api.py, tmdblist_api.py, etc.) own their auth lifecycle
(token refresh, device-code flows, revocation) and call get/post/delete here
for the actual HTTP work.

Adding a new service: add an entry to SERVICES, done.
"""

import time
import requests
from modules.settings_manager import get_setting


# ─────────────────────────────────────────────────────────────────────────────
# Service registry
# ─────────────────────────────────────────────────────────────────────────────

SERVICES = {
    "trakt": {
        "base_url": "https://api.trakt.tv/%s",
        "auth_style": "bearer",
        "token_key": "trakt.token",
        # Trakt requires these on every request
        "headers": lambda: {
            "Content-Type": "application/json",
            "trakt-api-version": "2",
            "trakt-api-key": get_setting("trakt.client"),
        },
    },
    "tmdb": {
        "base_url": "https://api.themoviedb.org/3/%s",
        "auth_style": "bearer",
        "token_key": "tmdb.token",
        "headers": lambda: {
            "accept": "application/json",
            "content-type": "application/json",
        },
    },
    "tmdb_v4": {
        "base_url": "https://api.themoviedb.org/4/%s",
        "auth_style": "bearer",
        "token_key": "tmdb.token",
        "headers": lambda: {
            "accept": "application/json",
            "content-type": "application/json",
        },
    },
    "real_debrid": {
        "base_url": lambda: "https://%s/rest/1.0/%%s" % (
            "app.real-debrid.com"
            if get_setting("rd.alternate_base_url") == "true"
            else "api.real-debrid.com"
        ),
        "auth_style": "bearer",
        "token_key": "rd.token",
    },
}


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────


def _build_url(cfg, endpoint):
    base = cfg["base_url"]
    return (base() if callable(base) else base) % endpoint


def _build_headers(cfg, with_auth):
    headers = cfg.get("headers", lambda: {})()
    if with_auth and cfg.get("auth_style") == "bearer":
        token = get_setting(cfg["token_key"])
        if token:
            headers["Authorization"] = "Bearer " + token
    return headers


def _send(fn, *args, **kwargs):
    """Send a request, retrying once after Retry-After on a 429."""
    resp = fn(*args, **kwargs)
    if resp.status_code == 429:
        retry_after = int(resp.headers.get("Retry-After", 1))
        time.sleep(retry_after)
        resp = fn(*args, **kwargs)
    return resp


def _parse(resp):
    if "json" in resp.headers.get("Content-Type", ""):
        return resp.json()
    return resp.text


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────


def get(service, endpoint, params=None, with_auth=True, timeout=10, raw=False):
    """
    GET endpoint on service, returns parsed body.
    Pass raw=True to get the Response object directly (e.g. to read pagination headers).
    """
    cfg = SERVICES[service]
    url = _build_url(cfg, endpoint)
    headers = _build_headers(cfg, with_auth)
    try:
        resp = _send(requests.get, url, params=params, headers=headers, timeout=timeout)
        if raw:
            return resp
        resp.raise_for_status()
        return _parse(resp)
    except Exception:
        return None


def post(service, endpoint, data=None, params=None, with_auth=True, timeout=10, raw=False, form=False):
    """
    POST to endpoint. Returns parsed body, or Response if raw=True.
    Pass form=True to send as application/x-www-form-urlencoded instead of JSON.
    """
    cfg = SERVICES[service]
    url = _build_url(cfg, endpoint)
    headers = _build_headers(cfg, with_auth)
    body_kwargs = {"data": data} if form else {"json": data}
    try:
        resp = _send(requests.post, url, params=params, headers=headers, timeout=timeout, **body_kwargs)
        if raw:
            return resp
        resp.raise_for_status()
        return _parse(resp)
    except Exception:
        return None


def put(service, endpoint, data=None, with_auth=True, timeout=10):
    """PUT to endpoint, body serialised as JSON. Returns parsed body."""
    cfg = SERVICES[service]
    url = _build_url(cfg, endpoint)
    headers = _build_headers(cfg, with_auth)
    try:
        resp = requests.put(url, json=data, headers=headers, timeout=timeout)
        resp.raise_for_status()
        return _parse(resp)
    except Exception:
        return None


def delete(service, endpoint, data=None, with_auth=True, timeout=10, raw=False):
    """DELETE endpoint. Returns parsed body, or Response if raw=True."""
    cfg = SERVICES[service]
    url = _build_url(cfg, endpoint)
    headers = _build_headers(cfg, with_auth)
    try:
        resp = requests.delete(url, json=data, headers=headers, timeout=timeout)
        if raw:
            return resp
        resp.raise_for_status()
        return _parse(resp)
    except Exception:
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Auth helpers (read-only — write logic lives in the api files)
# ─────────────────────────────────────────────────────────────────────────────


def get_token(service):
    return get_setting(SERVICES[service]["token_key"])


def is_authorized(service):
    return bool(get_token(service))
