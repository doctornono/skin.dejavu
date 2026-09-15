# -*- coding: utf-8 -*-
"""Enrich home items with DejaVu statuses and TMDb genre/cast/year."""

from __future__ import annotations

import json
import os
import sys
import time
import uuid
import urllib.error
import urllib.parse
import urllib.request

import xbmc
import xbmcaddon
import xbmcgui

from lib.store import STATUS_STALE, STATUS_TTL, TMDB_TTL, get as store_get, put as store_put, _schedule_revalidate

CACHE_TTL = TMDB_TTL
TMDB_FETCH_LIMIT = 12


def _tmdb_key():
    try:
        helper = xbmcaddon.Addon("plugin.video.themoviedb.helper").getAddonInfo("path")
        resources = os.path.join(helper, "resources")
        if resources not in sys.path:
            sys.path.insert(0, resources)
        from tmdbhelper.lib.api.api_keys.tmdb import API_KEY
        return API_KEY or ""
    except Exception:
        return ""


def tmdb_request(path, extra=None):
    key = _tmdb_key()
    if not key or not path:
        return {}
    lang = xbmc.getLanguage(xbmc.ISO_639_1) or "fr"
    query = {"api_key": key, "language": lang}
    if extra:
        query.update(extra)
    url = "https://api.themoviedb.org/3/%s?%s" % (path.lstrip("/"), urllib.parse.urlencode(query))
    try:
        request = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(request, timeout=8) as response:
            data = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, ValueError, TimeoutError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def _tmdb_get(kind, tmdb_id):
    tmdb_type = "tv" if kind in ("tv", "episode", "tvshow") else "movie"
    data = tmdb_request("%s/%s" % (tmdb_type, tmdb_id), {"append_to_response": "credits"})
    if not data:
        return {}
    genres = [g.get("name") for g in (data.get("genres") or []) if g.get("name")]
    year = (data.get("release_date") or data.get("first_air_date") or "")[:4]
    cast = [c.get("name") for c in (data.get("credits") or {}).get("cast") or [] if c.get("name")]
    return {
        "genre": " · ".join(genres[:3]),
        "year": year,
        "cast": ", ".join(cast[:4]),
        "title": data.get("title") or data.get("name") or "",
        "plot": data.get("overview") or "",
        "poster": ("https://image.tmdb.org/t/p/w500%s" % data["poster_path"]) if data.get("poster_path") else "",
        "fanart": ("https://image.tmdb.org/t/p/w1280%s" % data["backdrop_path"]) if data.get("backdrop_path") else "",
        "ts": int(time.time()),
    }


def enrich_tmdb(kind, tmdb_id, cache=None, budget=12):
    cache_key = "%s:%s" % ("tv" if kind in ("tv", "episode", "tvshow") else "movie", tmdb_id)
    cached, age = store_get("tmdb", cache_key)
    if isinstance(cached, dict) and age is not None and age < CACHE_TTL:
        if cache is not None:
            cache[cache_key] = cached
        return cached, budget
    if budget <= 0 or not tmdb_id:
        return cached or {}, budget
    meta = _tmdb_get(kind, tmdb_id)
    if meta:
        store_put("tmdb", cache_key, meta)
        if cache is not None:
            cache[cache_key] = meta
        return meta, budget - 1
    return cached or {}, budget


def _rpc_trim(value, depth=0):
    if depth > 5:
        return "..."
    if isinstance(value, dict):
        return {str(key): _rpc_trim(val, depth + 1) for key, val in list(value.items())[:40]}
    if isinstance(value, (list, tuple)):
        return [_rpc_trim(item, depth + 1) for item in value[:12]] + (["…+%s" % (len(value) - 12)] if len(value) > 12 else [])
    if isinstance(value, str) and len(value) > 500:
        return value[:500] + "…"
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return str(value)


def log_dejavu_rpc(kind, action, params, result):
    payload = {
        "kind": kind,
        "action": action,
        "params": _rpc_trim(params),
        "result": _rpc_trim(result),
        "result_type": type(result).__name__,
        "result_len": len(result) if isinstance(result, (list, dict, str)) else None,
    }
    text = json.dumps(payload, ensure_ascii=False, default=str)
    xbmc.log("[skin.dejavu.poc] DEJAVU RPC %s" % text[:16000], xbmc.LOGINFO)


def execute_jsonrpc(method, params=None, request_id=1):
    payload = {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params or {}}
    log_dejavu_rpc("JSONRPC.request", method, params, None)
    raw = xbmc.executeJSONRPC(json.dumps(payload))
    try:
        data = json.loads(raw)
    except ValueError:
        data = {"parse_error": (raw or "")[:400]}
    log_dejavu_rpc("JSONRPC.response", method, params, data)
    return data if isinstance(data, dict) else {}


def _acquire_dejavu_slot():
    home = xbmcgui.Window(10000)
    monitor = xbmc.Monitor()
    token = uuid.uuid4().hex[:12]
    deadline = time.time() + 45
    while time.time() < deadline:
        current = home.getProperty("dv.rpc.busy")
        if not current:
            home.setProperty("dv.rpc.busy", token)
            if home.getProperty("dv.rpc.busy") == token:
                return token
        if monitor.waitForAbort(0.08):
            break
    home.setProperty("dv.rpc.busy", token)
    return token


def _release_dejavu_slot(token):
    home = xbmcgui.Window(10000)
    if home.getProperty("dv.rpc.busy") == token:
        home.clearProperty("dv.rpc.busy")


def wrap_dejavu_client(client):
    original = client.call
    if getattr(client, "timeout", 0) < 20:
        client.timeout = 20

    def call(action, params=None):
        log_dejavu_rpc("NotifyAll.request", action, params, None)
        token = _acquire_dejavu_slot()
        try:
            result = original(action, params)
            if result is None:
                log_dejavu_rpc("NotifyAll.retry", action, params, {"reason": "timeout"})
                result = original(action, params)
        finally:
            _release_dejavu_slot(token)
        log_dejavu_rpc("NotifyAll.response", action, params, result)
        return result

    client.call = call
    return client


def _status_lookup_keys(item):
    kind = str(item.get("type") or "movie").lower()
    tmdb_id = item.get("id") or item.get("tmdbId") or ""
    show_id = item.get("tmdbId") or item.get("id") or ""
    keys = []
    if kind == "episode":
        season = item.get("season") or 0
        episode = item.get("episode") or 0
        if show_id and season and episode:
            keys.append("episode:%s:%s:%s" % (show_id, season, episode))
    if tmdb_id:
        keys.append("%s:%s" % ("tv" if kind in ("tv", "episode") else "movie", tmdb_id))
        keys.append(str(tmdb_id))
    return [str(key) for key in keys if key]


def _store_status_map(data):
    if not isinstance(data, dict):
        return
    for key, flags in data.items():
        if isinstance(flags, dict):
            store_put("status", str(key), flags)


def dejavu_status_map(payload):
    if not payload:
        return {}
    assembled = {}
    missing = []
    stale = False
    for item in payload:
        found = None
        age = None
        for key in _status_lookup_keys(item):
            cached, cached_age = store_get("status", key)
            if isinstance(cached, dict):
                found = (key, cached)
                age = cached_age
                assembled[key] = cached
                break
        if found is None:
            missing.append(item)
        elif age is not None and age >= STATUS_STALE:
            missing.append(item)
        elif age is not None and age >= STATUS_TTL:
            stale = True
    if not missing and not stale:
        return assembled
    if not missing and stale:
        _schedule_revalidate()
        return assembled
    to_fetch = missing[:24]
    try:
        addon_path = xbmcaddon.Addon("script.dejavu").getAddonInfo("path")
        lib_path = os.path.join(addon_path, "resources", "lib")
        if lib_path not in sys.path:
            sys.path.insert(0, lib_path)
        from client import DejaVuClient
        result = wrap_dejavu_client(DejaVuClient(timeout=20)).get_media_status(to_fetch)
    except Exception as exc:
        xbmc.log("[skin.dejavu.poc] dejaVu status failed: %s" % exc, xbmc.LOGDEBUG)
        log_dejavu_rpc("NotifyAll", "get_media_status", payload, {"error": str(exc)})
        return assembled
    if not isinstance(result, dict):
        return assembled
    data = result.get("data") if isinstance(result.get("data"), dict) else result
    if not isinstance(data, dict):
        return assembled
    _store_status_map(data)
    assembled.update(data)
    return assembled


def status_for(status_map, kind, tmdb_id, show_id="", season=0, episode=0):
    keys = []
    if kind == "episode" and show_id and season and episode:
        keys.append("episode:%s:%s:%s" % (show_id, season, episode))
    if tmdb_id:
        keys.append("%s:%s" % (("tv" if kind in ("tv", "episode") else "movie"), tmdb_id))
        keys.append(str(tmdb_id))
    for key in keys:
        flags = status_map.get(key)
        if isinstance(flags, dict) and flags:
            return flags
    return {}


def status_label(flags, watched_fallback=False, rating_fallback=""):
    parts = []
    if flags.get("watched") or watched_fallback:
        parts.append("Vu")
    if flags.get("inWatchlist"):
        parts.append("Liste")
    if flags.get("isFavorite"):
        parts.append("Favori")
    if flags.get("inCollection"):
        parts.append("Collection")
    rating = flags.get("rating") or rating_fallback
    if rating:
        parts.append("★ %s" % rating)
    return " · ".join(parts)
