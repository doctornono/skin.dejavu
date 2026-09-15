# -*- coding: utf-8 -*-
"""SQLite TTL cache for DejaVu lists, statuses and TMDb meta."""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import time

import xbmc
import xbmcgui
import xbmcvfs

TMDB_TTL = 7 * 24 * 3600
STATUS_TTL = 45
STATUS_STALE = 300

LIST_TTL = {
    "continue_watching": 30,
    "active_movie_scrobbles": 30,
    "active_tv_scrobbles": 30,
    "scrobbles": 30,
    "history": 60,
    "up_next": 60,
    "recent_watchlist": 120,
    "watchlist": 180,
    "favorites": 180,
    "ratings": 300,
    "collection": 300,
    "upcoming_releases": 600,
    "upcoming_schedule": 120,
    "list_items": 180,
}
LIST_TTL_DEFAULT = 120

_lock = threading.Lock()
_mem = {}
_pruned_at = 0


def _folder():
    path = xbmcvfs.translatePath("special://profile/addon_data/skin.dejavu.poc/")
    os.makedirs(path, exist_ok=True)
    return path


def _db_path():
    return os.path.join(_folder(), "dv_cache.sqlite")


def _connect():
    conn = sqlite3.connect(_db_path(), timeout=8, isolation_level=None)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS kv ("
        "ns TEXT NOT NULL, key TEXT NOT NULL, payload TEXT NOT NULL, ts INTEGER NOT NULL, "
        "PRIMARY KEY (ns, key))"
    )
    return conn


def _prune(conn):
    global _pruned_at
    now = int(time.time())
    if now - _pruned_at < 600:
        return
    _pruned_at = now
    cutoff = now - TMDB_TTL
    conn.execute("DELETE FROM kv WHERE ts < ?", (cutoff,))


def get(ns, key):
    mem_key = "%s:%s" % (ns, key)
    cached = _mem.get(mem_key)
    now = time.time()
    if cached:
        return cached[0], now - cached[1]
    with _lock:
        try:
            conn = _connect()
            try:
                _prune(conn)
                row = conn.execute(
                    "SELECT payload, ts FROM kv WHERE ns=? AND key=?",
                    (ns, key),
                ).fetchone()
            finally:
                conn.close()
        except sqlite3.Error as exc:
            xbmc.log("[skin.dejavu.poc] cache get failed: %s" % exc, xbmc.LOGDEBUG)
            return None, None
    if not row:
        return None, None
    try:
        payload = json.loads(row[0])
    except ValueError:
        return None, None
    ts = float(row[1] or 0)
    _mem[mem_key] = (payload, ts)
    return payload, now - ts


def put(ns, key, value):
    ts = int(time.time())
    mem_key = "%s:%s" % (ns, key)
    _mem[mem_key] = (value, ts)
    try:
        blob = json.dumps(value, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        return
    with _lock:
        try:
            conn = _connect()
            try:
                conn.execute(
                    "INSERT OR REPLACE INTO kv (ns, key, payload, ts) VALUES (?, ?, ?, ?)",
                    (ns, key, blob, ts),
                )
            finally:
                conn.close()
        except sqlite3.Error as exc:
            xbmc.log("[skin.dejavu.poc] cache put failed: %s" % exc, xbmc.LOGDEBUG)


def clear_ns(ns):
    prefix = ns + ":"
    for mem_key in list(_mem):
        if mem_key.startswith(prefix):
            _mem.pop(mem_key, None)
    with _lock:
        try:
            conn = _connect()
            try:
                conn.execute("DELETE FROM kv WHERE ns=?", (ns,))
            finally:
                conn.close()
        except sqlite3.Error as exc:
            xbmc.log("[skin.dejavu.poc] cache clear failed: %s" % exc, xbmc.LOGDEBUG)


def invalidate_user_data():
    clear_ns("list")
    clear_ns("status")


def list_ttl(action):
    return LIST_TTL.get(action or "", LIST_TTL_DEFAULT)


def list_stale(action):
    return max(list_ttl(action) * 10, 600)


def list_key(action, media_type, list_id, page=1):
    return "%s|%s|%s|%s" % (action or "", media_type or "", list_id or "", int(page or 1))


def _schedule_revalidate():
    home = xbmcgui.Window(10000)
    now = int(time.time())
    try:
        last = int(home.getProperty("dv.cache.revalidate_ts") or 0)
    except ValueError:
        last = 0
    if home.getProperty("dv.cache.revalidating") or now - last < 20:
        return
    home.setProperty("dv.cache.revalidating", "1")
    home.setProperty("dv.cache.revalidate_ts", str(now))
    xbmc.executebuiltin("RunScript(skin.dejavu.poc,revalidate_cache)")


def read_list(action, media_type, list_id, page=1):
    payload, age = get("list", list_key(action, media_type, list_id, page))
    if payload is None or age is None:
        return None, None
    return payload, age


def write_list(action, media_type, list_id, page, payload):
    put("list", list_key(action, media_type, list_id, page), payload)


def cached_list(action, media_type, list_id, page, loader):
    ttl = list_ttl(action)
    stale = list_stale(action)
    payload, age = read_list(action, media_type, list_id, page)
    if payload is not None and age is not None and _payload_has_items(payload):
        if age < ttl:
            return payload
        if age < stale:
            _schedule_revalidate()
            return payload
    try:
        fresh = loader()
    except Exception:
        if payload is not None:
            return payload
        raise
    if fresh:
        if not _payload_has_items(fresh):
            return payload if payload is not None else fresh
        write_list(action, media_type, list_id, page, fresh)
        return fresh
    if payload is not None:
        return payload
    return fresh


def _payload_has_items(payload):
    if isinstance(payload, dict) and "entries" in payload:
        return bool(payload.get("entries"))
    if isinstance(payload, list):
        return bool(payload)
    return bool(payload)


def refresh_home_lists():
    home = xbmcgui.Window(10000)
    if not xbmc.getCondVisibility("Window.IsVisible(Home)"):
        return
    try:
        slot = int(home.getProperty("dv.active.slot") or 0)
    except ValueError:
        slot = 0
    base = 111 + slot * 100
    for list_id in range(base, base + 8):
        xbmc.executebuiltin("Container(%s).Refresh" % list_id)
