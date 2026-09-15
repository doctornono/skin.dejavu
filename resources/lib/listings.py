# -*- coding: utf-8 -*-
"""Normalize mixed DejaVu widgets for Kodi (movie vs episode) and Alkoflix."""

from __future__ import annotations

import json
import os
import sys
import time
from urllib.parse import parse_qs, quote, unquote, urlencode, urlparse

import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin

from lib.meta import dejavu_status_map, enrich_tmdb, execute_jsonrpc, log_dejavu_rpc, status_for, status_label, tmdb_request, wrap_dejavu_client
from lib.store import cached_list
from lib.universes import UNIVERSES, universe_card, universe_entries


ACTIONS = (
    "continue_watching",
    "up_next",
    "recent_watchlist",
    "watchlist",
    "history",
    "favorites",
    "ratings",
    "collection",
    "scrobbles",
    "upcoming_releases",
    "upcoming_schedule",
    "active_movie_scrobbles",
    "active_tv_scrobbles",
    "list_items",
    "seasons",
    "episodes",
    "details_item",
    "details_collection",
    "details_in_lists",
    "details_cast",
    "open_details",
    "universes",
    "universe",
    "directory",
    "seeall",
    "list_next",
    "list_prev",
    "list_open",
    "nav_pages",
    "set_page",
)


_RPC_PROPERTIES = [
    "title",
    "plot",
    "year",
    "season",
    "episode",
    "showtitle",
    "runtime",
    "duration",
    "fanart",
    "thumbnail",
    "art",
    "file",
    "resume",
    "playcount",
    "userrating",
    "rating",
    "lastplayed",
    "genre",
    "director",
    "cast",
    "uniqueid",
    "premiered",
]


def _rpc(directory, media="files"):
    data = execute_jsonrpc("Files.GetDirectory", {
        "directory": directory,
        "media": media,
        "properties": list(_RPC_PROPERTIES),
    })
    return (data.get("result") or {}).get("files") or []


def _rpc_listing(directory):
    files = _rpc(directory, "video")
    if files:
        return files
    return _rpc(directory, "files")


def _first(values):
    if not values:
        return ""
    value = values[0] if isinstance(values, list) else values
    return "" if value is None else str(value)


def _query(file_url):
    return {key: _first(val) for key, val in parse_qs(urlparse(file_url or "").query).items()}


def _as_int(value):
    try:
        number = int(float(str(value).strip()))
    except (TypeError, ValueError):
        return 0
    return number if number > 0 else 0


def _art(entry):
    art = entry.get("art") if isinstance(entry.get("art"), dict) else {}
    fanart = art.get("fanart") or entry.get("fanart") or ""
    poster = art.get("poster") or art.get("thumb") or entry.get("thumbnail") or ""
    return {
        "fanart": fanart or poster,
        "poster": poster,
        "thumb": art.get("landscape") or fanart or poster,
        "icon": poster,
    }


def _percent(entry, query):
    resume = entry.get("resume") if isinstance(entry.get("resume"), dict) else {}
    position = float(resume.get("position") or 0)
    total = float(resume.get("total") or entry.get("runtime") or entry.get("duration") or 0)
    raw = _as_int(query.get("progress"))
    if 0 < position and total > position:
        return max(1, min(99, int(round(100.0 * position / total))))
    if 0 < raw <= 100:
        return raw
    return 0


def _unique_ids(entry):
    unique = entry.get("uniqueid") if isinstance(entry.get("uniqueid"), dict) else {}
    return {str(key).lower(): "" if value is None else str(value) for key, value in unique.items()}


def _kind(entry, query):
    media_type = (
        query.get("type")
        or query.get("media_type")
        or query.get("content")
        or entry.get("type")
        or entry.get("mimetype")
        or ""
    ).lower()
    season = _as_int(query.get("season") or entry.get("season"))
    episode = _as_int(query.get("episode") or entry.get("episode"))
    if media_type in ("episode",) or (season and episode):
        return "episode", season, episode
    if media_type in ("tv", "tvshow", "show", "series"):
        return "tv", season, episode
    return "movie", 0, 0


def _tmdb_ids(entry, query, kind):
    unique = _unique_ids(entry)
    tmdb = (
        query.get("tmdb_id")
        or query.get("tmdbid")
        or query.get("tmdb")
        or unique.get("tmdb")
        or unique.get("tmdb_id")
        or ""
    )
    show = (
        query.get("show_tmdb_id")
        or query.get("tvshow_tmdb_id")
        or unique.get("tvshow.tmdb")
        or unique.get("tvshow_tmdb")
        or ""
    )
    if kind in ("episode", "tv"):
        play_id = show or tmdb
        return str(play_id or ""), str(tmdb or ""), str(show or play_id or "")
    return str(tmdb or ""), "", str(tmdb or "")


def _play_url(kind, play_id, title, showtitle, season, episode, ep_name):
    if kind == "episode" and season and episode and play_id:
        params = {
            "mode": "tmdbh_select",
            "media_type": "episode",
            "tmdb_id": play_id,
            "season": str(season),
            "episode": str(episode),
            "query": showtitle or title,
            "ep_name": ep_name or title,
            "autoplay": "false",
        }
    elif kind == "tv" and play_id:
        params = {
            "mode": "tmdbh_select",
            "media_type": "tv",
            "tmdb_id": play_id,
            "query": showtitle or title,
            "title": title,
            "autoplay": "false",
        }
    else:
        params = {
            "mode": "tmdbh_select",
            "media_type": "movie",
            "tmdb_id": play_id,
            "query": title,
            "title": title,
            "autoplay": "false",
        }
    return "plugin://plugin.video.alkoflix/?%s" % urlencode(params)


def _rating_label(entry):
    user = _as_int(entry.get("userrating"))
    if user:
        return "★ %s" % user
    try:
        public = float(entry.get("rating") or 0)
    except (TypeError, ValueError):
        public = 0.0
    if public >= 0.5:
        return "★ %.1f" % public
    return ""


def _join_names(value):
    if isinstance(value, list):
        names = []
        for item in value:
            if isinstance(item, dict):
                names.append(item.get("name") or item.get("title") or "")
            else:
                names.append(str(item))
        return ", ".join([name for name in names if name])
    return str(value or "")


def _build_item(entry, tmdb_meta=None, flags=None):
    query = _query(entry.get("file"))
    kind, season, episode = _kind(entry, query)
    play_id, episode_tmdb, show_tmdb = _tmdb_ids(entry, query, kind)
    title = entry.get("title") or entry.get("label") or ""
    showtitle = entry.get("showtitle") or query.get("title") or ""
    if kind == "episode" and not showtitle:
        showtitle = title
    dbtype = "episode" if kind == "episode" else ("tvshow" if kind == "tv" else "movie")
    percent = _percent(entry, query)
    playcount = _as_int(entry.get("playcount"))
    userrating = _as_int(entry.get("userrating") or (flags or {}).get("rating"))
    rating_label = _rating_label(entry)
    if not rating_label and userrating:
        rating_label = "★ %s" % userrating
    tmdb_meta = tmdb_meta or {}
    flags = flags or {}
    watched = playcount > 0 or bool(flags.get("watched"))
    year = _as_int(entry.get("year") or tmdb_meta.get("year"))
    genre = tmdb_meta.get("genre") or _join_names(entry.get("genre"))
    cast = tmdb_meta.get("cast") or _join_names(entry.get("cast"))
    item = xbmcgui.ListItem(label=title, offscreen=True)
    info = {
        "title": title,
        "plot": entry.get("plot") or "",
        "mediatype": dbtype,
        "playcount": 1 if watched else playcount,
    }
    if year:
        info["year"] = year
    if userrating:
        info["userrating"] = userrating
    if genre:
        info["genre"] = genre
    if kind == "episode":
        info["tvshowtitle"] = showtitle
        info["season"] = season
        info["episode"] = episode
    item.setInfo("video", info)
    item.setArt(_art(entry))
    item.setProperty("DBType", dbtype)
    item.setProperty("media_type", "episode" if kind == "episode" else ("tv" if kind == "tv" else "movie"))
    item.setProperty("tmdb_type", "tv" if kind in ("tv", "episode") else "movie")
    item.setProperty("tmdb_id", play_id)
    item.setProperty("TmdbId", play_id)
    if show_tmdb:
        item.setProperty("tvshow_tmdb_id", show_tmdb)
    if episode_tmdb:
        item.setProperty("episode_tmdb_id", episode_tmdb)
    item.setProperty("PercentPlayed", str(percent))
    item.setProperty("PercentBarWidth", str(max(0, min(260, int(round(260 * percent / 100.0))))))
    item.setProperty("UserRating", str(userrating) if userrating else "")
    item.setProperty("RatingLabel", rating_label)
    item.setProperty("Watched", "true" if watched else "false")
    item.setProperty("WatchedLabel", "Vu" if watched else "")
    item.setProperty("GenreLabel", genre)
    item.setProperty("CastLabel", cast)
    item.setProperty("YearLabel", str(year) if year else "")
    item.setProperty("StatusLabel", status_label(flags, watched_fallback=watched, rating_fallback=userrating or ""))
    play_url = _play_url(kind, play_id, title, showtitle, season, episode, title)
    item.setProperty("play_url", play_url)
    item.setProperty("IsPlayable", "false")
    if play_id:
        try:
            item.setUniqueIDs({"tmdb": play_id}, "tmdb")
        except Exception:
            pass
    return item, play_url


def _dejavu_libs():
    addon_path = xbmcaddon.Addon("script.dejavu").getAddonInfo("path")
    lib_path = os.path.join(addon_path, "resources", "lib")
    if lib_path not in sys.path:
        sys.path.insert(0, lib_path)
    from client import DejaVuClient
    from pure import list_rows_from_result
    return wrap_dejavu_client(DejaVuClient(timeout=20)), list_rows_from_result


def _raw_to_entry(raw):
    if not isinstance(raw, dict):
        return None
    info = raw.get("info") if isinstance(raw.get("info"), dict) else {}
    art = raw.get("art") if isinstance(raw.get("art"), dict) else {}
    media_type = str(raw.get("type") or info.get("mediatype") or "movie").lower()
    if media_type in ("tv", "tvshow", "show", "series"):
        media_type = "tv"
    elif media_type != "episode":
        media_type = "movie"
    tmdb = raw.get("tmdbId") or raw.get("tmdb_id") or info.get("tmdbId") or raw.get("id")
    show = raw.get("tvShowId") or raw.get("showTmdbId") or raw.get("show_tmdb_id") or info.get("tvShowId")
    title = info.get("title") or raw.get("title") or raw.get("name") or ""
    if not title and not tmdb:
        return None
    season = raw.get("seasonNumber") or raw.get("season") or info.get("season")
    episode = raw.get("episodeNumber") or raw.get("episode") or info.get("episode")
    params = {"action": "play", "type": media_type, "tmdb_id": tmdb or "", "title": title}
    if show:
        params["show_tmdb_id"] = show
    if season not in (None, ""):
        params["season"] = season
    if episode not in (None, ""):
        params["episode"] = episode
    file_url = "plugin://script.dejavu/?%s" % urlencode({key: str(val) for key, val in params.items() if val not in (None, "")})
    poster = art.get("poster") or raw.get("posterUrl") or ""
    fanart = art.get("fanart") or raw.get("backdropUrl") or ""
    return {
        "filetype": "file",
        "file": file_url,
        "title": title,
        "label": title,
        "plot": info.get("plot") or raw.get("overview") or "",
        "year": info.get("year") or raw.get("year"),
        "season": season,
        "episode": episode,
        "showtitle": info.get("tvshowtitle") or raw.get("showTitle") or "",
        "fanart": fanart,
        "thumbnail": poster,
        "art": {"fanart": fanart, "poster": poster, "thumb": fanart or poster},
        "type": media_type,
        "uniqueid": {"tmdb": str(tmdb or "")},
        "resume": {"position": 0, "total": raw.get("duration") or info.get("duration") or 0},
        "playcount": 1 if raw.get("watched") else 0,
        "userrating": raw.get("rating") or info.get("userrating") or 0,
        "rating": info.get("rating") or 0,
        "genre": info.get("genre") or [],
        "cast": info.get("cast") or [],
    }


LIST_PAGE_SIZE = 20
PAGED_ACTIONS = (
    "continue_watching",
    "up_next",
    "watchlist",
    "history",
    "recent_watchlist",
    "favorites",
    "ratings",
    "collection",
    "scrobbles",
    "upcoming_releases",
    "upcoming_schedule",
    "active_movie_scrobbles",
    "active_tv_scrobbles",
    "list_items",
)
DASHBOARD_ACTIONS = {
    "continue_watching": "continue_watching",
    "recent_watchlist": "recent_watchlist",
    "upcoming_releases": "upcoming_releases",
    "upcoming_schedule": "upcoming_schedule",
    "active_movie_scrobbles": "active_movie_scrobbles",
    "active_tv_scrobbles": "active_tv_scrobbles",
}
PLUGIN_RPC_ACTIONS = {
    "up_next",
    "watchlist",
    "history",
    "favorites",
    "scrobbles",
}


def _extract_rows(result, list_rows):
    rows, pagination = _extract_rows_paged(result, list_rows)
    return rows


def _extract_rows_paged(result, list_rows):
    rows, pagination = list_rows(result)
    if rows:
        return rows, pagination or {}
    data = result.get("data") if isinstance(result, dict) else result
    if isinstance(data, dict):
        nested = data.get("pagination") if isinstance(data.get("pagination"), dict) else {}
        for value in data.values():
            if isinstance(value, list) and value:
                return value, pagination or nested or {}
    return [], pagination or {}


def _has_more(pagination, count=0):
    if isinstance(pagination, dict):
        if pagination.get("hasMore") is False or pagination.get("has_more") is False:
            return False
        if pagination.get("hasMore") is True or pagination.get("has_more") is True:
            return True
        page = _as_int(pagination.get("page")) or 1
        total = _as_int(
            pagination.get("totalPages")
            or pagination.get("total_pages")
            or pagination.get("pages")
        )
        if total:
            return page < total
    return count >= LIST_PAGE_SIZE


def _page_number(value):
    return _as_int(value) or 1


def _skin_list_url(action, media_type, page, list_id=""):
    params = {"action": action, "page": str(max(1, page))}
    if media_type:
        params["type"] = media_type
    if list_id:
        params["list_id"] = list_id
    return "plugin://skin.dejavu.poc/?%s" % urlencode(params)


def _dejavu_plugin_url(action, media_type, page, list_id=""):
    params = {"action": action, "page": str(max(1, page))}
    if media_type:
        params["type"] = media_type
    if list_id:
        params["list_id"] = list_id
    return "plugin://script.dejavu/?%s" % urlencode(params)


def _api_result(api, list_rows, action, media_type, list_id=""):
    entries, _pagination = _api_page(api, list_rows, action, media_type, 1, list_id)
    return entries


def _media_from_rpc(directory):
    files = _rpc_listing(directory)
    entries = []
    for entry in files:
        file_url = entry.get("file") or ""
        if _is_more_item(entry):
            continue
        if entry.get("filetype") == "directory" and "tmdb_id=" not in file_url and "action=play" not in file_url:
            continue
        entries.append(entry)
    return entries


def _fetch_rows_uncached(action, media_type, list_id=""):
    entries = _fetch_api(action, media_type, list_id)
    if entries:
        return entries
    if action == "watchlist" and not media_type:
        return _media_from_rpc("plugin://script.dejavu/?action=watchlist&type=movie") + _media_from_rpc(
            "plugin://script.dejavu/?action=watchlist&type=tv"
        )
    if action in PLUGIN_RPC_ACTIONS:
        return _media_from_rpc(_dejavu_plugin_url(action, media_type, 1, list_id))
    return []


def _fetch_rows(action, media_type, list_id=""):
    return cached_list(action, media_type, list_id, 1, lambda: _fetch_rows_uncached(action, media_type, list_id))


def _fetch_api(action, media_type, list_id=""):
    try:
        api, list_rows = _dejavu_libs()
        if action == "watchlist" and media_type == "tv":
            entries = _api_result(api, list_rows, "watchlist", "tv")
            if not entries:
                mixed = _api_result(api, list_rows, "watchlist", "all")
                entries = [entry for entry in mixed if entry.get("type") in ("tv", "episode")]
        elif action == "watchlist" and not media_type:
            entries = _api_result(api, list_rows, "watchlist", "movie")
            entries.extend(_api_result(api, list_rows, "watchlist", "tv"))
        else:
            entries = _api_result(api, list_rows, action, media_type, list_id)
        return [entry for entry in entries if entry]
    except Exception as exc:  # noqa: BLE001
        xbmc.log("[skin.dejavu.poc] dejavu api failed: %s" % exc, xbmc.LOGDEBUG)
        return []


def _api_page(api, list_rows, action, media_type, page, list_id=""):
    page_size = LIST_PAGE_SIZE
    if action == "list_items":
        result = api.get_list_items(list_id, page=page, page_size=page_size, minimal=False)
    elif action in DASHBOARD_ACTIONS:
        result = api.get_dashboard_widget(
            DASHBOARD_ACTIONS[action],
            list_id=list_id or None,
            page=page,
            page_size=page_size,
            minimal=False,
        )
    elif action == "up_next":
        result = api.get_up_next(page=page, page_size=page_size, minimal=False)
    elif action == "history":
        result = api.get_history(
            media_type=media_type or "movie",
            page=page,
            page_size=page_size,
            sort="watchedAt:desc",
            minimal=False,
        )
    elif action == "favorites":
        result = api.get_favorites(media_type=media_type or None, page=page, page_size=page_size, minimal=False)
    elif action == "ratings":
        result = api.get_ratings(media_type=media_type or None, page=page, page_size=page_size, minimal=False)
    elif action == "collection":
        result = api.get_collection(
            media_type=media_type or None,
            page=page,
            page_size=page_size,
            sort="addedAt:desc",
            minimal=False,
        )
    elif action == "scrobbles":
        result = api.get_scrobbles(media_type=media_type or None, page=page, page_size=page_size, minimal=False)
    else:
        page_size = 100 if action == "watchlist" and media_type in ("tv", "all") and page == 1 else LIST_PAGE_SIZE
        result = api.get_watchlist(
            media_type=media_type or None,
            page=page,
            page_size=page_size,
            sort="addedAt:desc",
            minimal=False,
        )
    rows, pagination = _extract_rows_paged(result, list_rows)
    if result is None:
        pagination = dict(pagination or {})
        pagination["_rpc_timeout"] = True
    entries = [entry for entry in (_raw_to_entry(raw) for raw in (rows or [])) if entry]
    return entries, pagination


def _fetch_paged_uncached(action, media_type, page, list_id=""):
    page = _page_number(page)
    try:
        api, list_rows = _dejavu_libs()
        entries, pagination = _api_page(api, list_rows, action, media_type, page, list_id)
        if action == "watchlist" and media_type == "tv" and not entries:
            mixed, pagination = _api_page(api, list_rows, "watchlist", "all", page)
            entries = [entry for entry in mixed if entry.get("type") in ("tv", "episode")]
        if entries:
            next_url = ""
            if _has_more(pagination, len(entries)):
                current = _as_int(pagination.get("page")) or page
                next_url = _skin_list_url(action, media_type, current + 1, list_id)
            return entries, next_url, False
        if (pagination or {}).get("_rpc_timeout"):
            log_dejavu_rpc("NotifyAll", action, {"page": page, "type": media_type}, {"skipped_plugin_fallback": True, "reason": "rpc_timeout"})
            return [], "", False
    except Exception as exc:  # noqa: BLE001
        xbmc.log("[skin.dejavu.poc] dejavu paged api failed: %s" % exc, xbmc.LOGDEBUG)
        log_dejavu_rpc("NotifyAll", action, {"page": page, "type": media_type}, {"error": str(exc), "skipped_plugin_fallback": True})
        return [], "", False
    if action in PLUGIN_RPC_ACTIONS:
        return _media_from_rpc(_dejavu_plugin_url(action, media_type, page, list_id)), "", True
    return [], "", False


def _fetch_paged(action, media_type, page, list_id=""):
    page = _page_number(page)

    def _load():
        entries, next_url, rpc = _fetch_paged_uncached(action, media_type, page, list_id)
        return {"entries": entries, "next_url": next_url, "rpc": rpc}

    packed = cached_list(action, media_type, list_id, page, _load)
    if isinstance(packed, dict) and "entries" in packed:
        return packed.get("entries") or [], packed.get("next_url") or "", bool(packed.get("rpc"))
    return [], "", False


def warm_home_rails(rails, force=False):
    from lib.store import write_list

    for rail in rails or []:
        if (rail.get("source") or "dejavu") != "dejavu":
            continue
        action = rail.get("action") or "watchlist"
        media = rail.get("type") or ""
        list_id = rail.get("list_id") or ""
        if force:
            entries = _fetch_rows_uncached(action, media, list_id)
            if entries:
                write_list(action, media, list_id, 1, entries)
        else:
            _fetch_rows(action, media, list_id)


def _poster_url(path):
    if not path:
        return ""
    if str(path).startswith("http"):
        return path
    return "https://image.tmdb.org/t/p/w500%s" % path


def _fanart_url(path):
    if not path:
        return ""
    if str(path).startswith("http"):
        return path
    return "https://image.tmdb.org/t/p/w1280%s" % path


def _apply_flags(item, flags, watched=False, rating=0):
    flags = flags or {}
    seen = watched or bool(flags.get("watched"))
    item.setProperty("Watched", "true" if seen else "false")
    item.setProperty("WatchedLabel", "Vu" if seen else "")
    item.setProperty("inWatchlist", "true" if flags.get("inWatchlist") else "false")
    item.setProperty("isFavorite", "true" if flags.get("isFavorite") else "false")
    item.setProperty("inCollection", "true" if flags.get("inCollection") else "false")
    item.setProperty("StatusLabel", status_label(flags, watched_fallback=seen, rating_fallback=rating or flags.get("rating") or ""))


def _dispatch_seasons(handle, tmdb_id):
    show = tmdb_request("tv/%s" % tmdb_id, {"append_to_response": "credits"})
    show_title = (show or {}).get("name") or ""
    fanart = _fanart_url((show or {}).get("backdrop_path"))
    rows = (show or {}).get("seasons") or []
    payload = [{"type": "tv", "id": _as_int(tmdb_id)}]
    status_map = dejavu_status_map(payload)
    flags = status_for(status_map, "tv", tmdb_id)
    for raw in rows:
        number = raw.get("season_number")
        try:
            season = int(number)
        except (TypeError, ValueError):
            continue
        if season < 1:
            continue
        title = raw.get("name") or "Saison %s" % season
        poster = _poster_url(raw.get("poster_path") or (show or {}).get("poster_path"))
        item = xbmcgui.ListItem(label=title, offscreen=True)
        item.setInfo("video", {"title": title, "tvshowtitle": show_title, "season": season, "mediatype": "season", "plot": raw.get("overview") or ""})
        item.setArt({"poster": poster, "thumb": poster, "fanart": fanart})
        item.setProperty("tmdb_id", str(tmdb_id))
        item.setProperty("tvshow_tmdb_id", str(tmdb_id))
        item.setProperty("media_type", "tv")
        item.setProperty("DBType", "season")
        _apply_flags(item, flags)
        play_url = _play_url("tv", tmdb_id, show_title, show_title, 0, 0, "")
        item.setProperty("play_url", play_url)
        xbmcplugin.addDirectoryItem(handle, play_url, item, False)


def _dispatch_episodes(handle, tmdb_id, season):
    season = season or 1
    show = tmdb_request("tv/%s" % tmdb_id)
    data = tmdb_request("tv/%s/season/%s" % (tmdb_id, season))
    show_title = (show or {}).get("name") or (data or {}).get("name") or ""
    fanart = _fanart_url((show or {}).get("backdrop_path"))
    rows = (data or {}).get("episodes") or []
    payload = [{"type": "tv", "id": _as_int(tmdb_id)}]
    for raw in rows:
        ep_num = _as_int(raw.get("episode_number"))
        if ep_num:
            payload.append({
                "type": "episode",
                "id": _as_int(raw.get("id")),
                "tmdbId": _as_int(tmdb_id),
                "season": season,
                "episode": ep_num,
            })
    status_map = dejavu_status_map(payload)
    for raw in rows:
        ep_num = _as_int(raw.get("episode_number"))
        if not ep_num:
            continue
        title = raw.get("name") or "Épisode %s" % ep_num
        still = _poster_url(raw.get("still_path") or (show or {}).get("backdrop_path"))
        play_url = _play_url("episode", tmdb_id, title, show_title, season, ep_num, title)
        item = xbmcgui.ListItem(label=title, offscreen=True)
        item.setInfo("video", {
            "title": title,
            "tvshowtitle": show_title,
            "season": season,
            "episode": ep_num,
            "mediatype": "episode",
            "plot": raw.get("overview") or "",
        })
        item.setArt({"thumb": still, "fanart": fanart, "poster": still})
        item.setProperty("tmdb_id", str(tmdb_id))
        item.setProperty("tvshow_tmdb_id", str(tmdb_id))
        item.setProperty("media_type", "episode")
        item.setProperty("DBType", "episode")
        item.setProperty("play_url", play_url)
        flags = status_for(status_map, "episode", tmdb_id, tmdb_id, season, ep_num)
        _apply_flags(item, flags, watched=bool(raw.get("watched")))
        try:
            item.setUniqueIDs({"tmdb": str(tmdb_id)}, "tmdb")
        except Exception:
            pass
        xbmcplugin.addDirectoryItem(handle, play_url, item, False)


def _dispatch_details_item(handle, params):
    media_type = (_first(params.get("type")) or "movie").lower()
    kind = "tv" if media_type in ("tv", "tvshow", "episode", "season") else "movie"
    tmdb_id = _first(params.get("tmdb_id"))
    show_id = _first(params.get("show_tmdb_id")) or tmdb_id
    season = _as_int(_first(params.get("season")))
    episode = _as_int(_first(params.get("episode")))
    if kind == "episode" or (season and episode):
        kind = "episode"
        tmdb_id = show_id
    tmdb_meta, _budget = enrich_tmdb("tv" if kind in ("tv", "episode") else "movie", show_id or tmdb_id, None, 1)
    title = _first(params.get("title")) or tmdb_meta.get("title") or ""
    play_id = show_id or tmdb_id
    play_url = _play_url(kind if kind != "episode" else "episode", play_id, title, title, season, episode, title)
    if kind == "tv":
        play_url = _play_url("tv", play_id, title, title, 0, 0, "")
    if kind == "movie":
        play_url = _play_url("movie", play_id, title, "", 0, 0, "")
    payload = [{"type": "tv" if kind in ("tv", "episode") else "movie", "id": _as_int(play_id)}]
    if kind == "episode" and season and episode:
        payload.append({"type": "episode", "id": _as_int(tmdb_id), "tmdbId": _as_int(play_id), "season": season, "episode": episode})
    flags = status_for(dejavu_status_map(payload), kind, play_id, play_id, season, episode)
    item = xbmcgui.ListItem(label=title, offscreen=True)
    dbtype = "episode" if kind == "episode" else ("tvshow" if kind == "tv" else "movie")
    info = {"title": title, "mediatype": dbtype, "plot": tmdb_meta.get("plot") or ""}
    if season:
        info["season"] = season
    if episode:
        info["episode"] = episode
        info["tvshowtitle"] = title
    item.setInfo("video", info)
    item.setArt({"fanart": tmdb_meta.get("fanart") or "", "poster": tmdb_meta.get("poster") or "", "thumb": tmdb_meta.get("poster") or ""})
    item.setProperty("tmdb_id", str(play_id))
    item.setProperty("TmdbId", str(play_id))
    item.setProperty("tvshow_tmdb_id", str(play_id) if kind in ("tv", "episode") else "")
    item.setProperty("media_type", "episode" if kind == "episode" else ("tv" if kind == "tv" else "movie"))
    item.setProperty("DBType", dbtype)
    item.setProperty("play_url", play_url)
    _apply_flags(item, flags)
    try:
        item.setUniqueIDs({"tmdb": str(play_id)}, "tmdb")
    except Exception:
        pass
    xbmcplugin.addDirectoryItem(handle, play_url, item, False)


def _dispatch_universes(handle):
    xbmcplugin.setContent(handle, "videos")
    for spec in UNIVERSES:
        card = universe_card(spec)
        item = xbmcgui.ListItem(label=card["label"], offscreen=True)
        item.setInfo("video", {"title": card["label"], "plot": card["plot"], "mediatype": "set"})
        item.setArt({
            "fanart": card["fanart"],
            "poster": card["poster"],
            "thumb": card["thumb"],
            "icon": card["poster"] or card["thumb"],
        })
        item.setProperty("universe_id", card["id"])
        item.setProperty("SubtitleLabel", card["subtitle"])
        item.setProperty("IsFolder", "true")
        url = "plugin://skin.dejavu.poc/?action=universe&id=%s" % card["id"]
        item.setProperty("FolderPath", url)
        xbmcplugin.addDirectoryItem(handle, url, item, False)
    xbmcplugin.endOfDirectory(handle, cacheToDisc=False)


def _dispatch_universe(handle, universe_id):
    xbmcplugin.setContent(handle, "videos")
    rows = universe_entries(universe_id)
    budget = 12
    status_payload = []
    parsed = []
    for entry in rows:
        query = _query(entry.get("file"))
        kind, season, episode = _kind(entry, query)
        play_id, _episode_tmdb, show_tmdb = _tmdb_ids(entry, query, kind)
        parsed.append((entry, kind, season, episode, play_id, show_tmdb))
        if play_id:
            status_payload.append({"type": "tv" if kind == "tv" else "movie", "id": _as_int(play_id)})
    status_map = dejavu_status_map(status_payload)
    for entry, kind, season, episode, play_id, show_tmdb in parsed:
        tmdb_meta, budget = enrich_tmdb(kind, show_tmdb or play_id, None, budget)
        flags = status_for(status_map, kind, play_id, show_tmdb, season, episode)
        item, play_url = _build_item(entry, tmdb_meta=tmdb_meta, flags=flags)
        xbmcplugin.addDirectoryItem(handle, play_url, item, False)
    xbmcplugin.endOfDirectory(handle, cacheToDisc=False)


def _dispatch_nav_pages(handle):
    from lib.pages import nav_items

    xbmcplugin.setContent(handle, "files")
    for row in nav_items():
        item = xbmcgui.ListItem(label=row["label"], offscreen=True)
        item.setArt({"icon": row["icon"], "thumb": row["icon"]})
        item.setProperty("nav_action", row["nav_action"])
        item.setProperty("page_id", row.get("page_id") or "")
        url = "plugin://skin.dejavu.poc/?action=nav_pages&page=%s" % (row.get("page_id") or row["label"])
        xbmcplugin.addDirectoryItem(handle, url, item, False)
    xbmcplugin.endOfDirectory(handle, cacheToDisc=False)


def _folder_item(entry):
    title = entry.get("label") or entry.get("title") or entry.get("file") or ""
    file_url = entry.get("file") or ""
    item = xbmcgui.ListItem(label=title, offscreen=True)
    item.setInfo("video", {"title": title, "plot": entry.get("plot") or ""})
    item.setArt(_art(entry))
    item.setProperty("IsFolder", "true")
    item.setProperty("FolderPath", file_url)
    item.setProperty("media_type", "folder")
    return item


def _norm_label(value):
    text = (value or "").strip().lower().replace("…", "...")
    return text.rstrip(".")


_NAV_MODES = {
    "navigator",
    "build_movie_list",
    "build_tvshow_list",
    "build_season_list",
    "build_episode_list",
    "build_navigate",
}


def _has_media_art(entry):
    art = _art(entry)
    for key in ("poster", "fanart", "thumb"):
        value = (art.get(key) or "").lower()
        if value.startswith("http") or value.startswith("image://") or "/t/p/" in value:
            return True
    return False


def _is_title_entry(entry, query, play_id):
    if play_id:
        return True
    if entry.get("filetype") != "directory":
        return True
    mode = (query.get("mode") or "").lower()
    if mode in ("play_media", "tmdbh_select", "tmdbh_play", "tmdbh_options", "info_extra_choice", "playback"):
        return True
    if mode in _NAV_MODES:
        return False
    if query.get("action") and "tmdb_id" not in query and not _has_media_art(entry):
        return False
    return _has_media_art(entry) or bool(entry.get("year") or entry.get("plot") or entry.get("premiered"))


def _url_page(path):
    query = _query(path)
    for key in ("page", "page_no", "pageno", "nextpage", "next_page", "start"):
        number = _as_int(query.get(key))
        if number:
            return number
    return 0


def _is_more_label(title):
    if not title:
        return False
    if title in (
        "plus",
        "plus...",
        "more",
        "more...",
        "next",
        "next page",
        "nextpage",
        "page suivante",
        "page suivant",
        "page next",
    ):
        return True
    if "page suivante" in title or "page suivant" in title or "next page" in title:
        return True
    if title.startswith("next") or title.endswith("suivant") or title.endswith("suivante"):
        return True
    return False


def _is_more_item(entry, listing_path=""):
    title = _norm_label(entry.get("label") or entry.get("title") or "")
    if _is_more_label(title):
        return True
    for string_id in (22082, 33078):
        localized = _norm_label(xbmc.getLocalizedString(string_id))
        if localized and (title == localized or localized in title):
            return True
    file_url = entry.get("file") or ""
    lower = file_url.lower()
    if "nextpage" in lower or "next_page=" in lower or "info=next" in lower or "widget=next" in lower:
        return True
    art = entry.get("art") if isinstance(entry.get("art"), dict) else {}
    for key in ("icon", "thumb", "landscape", "poster", "fanart"):
        value = (art.get(key) or "").lower()
        if "nextpage" in value or "next_page" in value:
            return True
    next_page = _url_page(file_url)
    current_page = _url_page(listing_path) or 1
    if (
        next_page > current_page
        and entry.get("filetype") == "directory"
        and not _has_media_art(entry)
        and not _tmdb_ids(entry, _query(file_url), "movie")[0]
    ):
        return True
    return False


def _home_window():
    return xbmcgui.Window(10000)


def _set_list_next(url):
    home = _home_window()
    if url:
        home.setProperty("dv.list.next", url)
    else:
        home.clearProperty("dv.list.next")


def _push_list_path(home, path):
    if not path:
        return
    stack = home.getProperty("dv.list.stack")
    home.setProperty("dv.list.stack", "%s\n%s" % (stack, path) if stack else path)
    home.setProperty("dv.list.prev", path)


def _pop_list_path(home):
    stack = home.getProperty("dv.list.stack")
    if not stack:
        home.clearProperty("dv.list.prev")
        return ""
    parts = stack.split("\n")
    last = parts.pop()
    home.setProperty("dv.list.stack", "\n".join(parts))
    if parts:
        home.setProperty("dv.list.prev", parts[-1])
    else:
        home.clearProperty("dv.list.prev")
        home.clearProperty("dv.list.stack")
    return last


def _refresh_listing():
    xbmc.executebuiltin("Container.Refresh")


def _navigate_list(path, title=None, push=True):
    home = _home_window()
    current = home.getProperty("dv.list.path")
    if push and current and current != path:
        _push_list_path(home, current)
    if title:
        home.setProperty("dv.list.title", title)
    home.setProperty("dv.list.path", path or "")
    home.clearProperty("dv.list.next")
    try:
        rev = int(home.getProperty("dv.list.rev") or 0) + 1
    except ValueError:
        rev = 1
    home.setProperty("dv.list.rev", str(rev))
    if xbmc.getCondVisibility("Window.IsVisible(1116)"):
        _refresh_listing()
    else:
        xbmc.executebuiltin("ActivateWindow(1116)")


def _publish_listing(handle, files, capture_nav=False, listing_path=""):
    xbmcplugin.setContent(handle, "videos")
    next_url = ""
    playable = []
    for entry in files or []:
        if _is_more_item(entry, listing_path):
            if not next_url:
                next_url = entry.get("file") or ""
            continue
        file_url = entry.get("file") or ""
        query = _query(file_url)
        kind, season, episode = _kind(entry, query)
        play_id, _episode_tmdb, _show_tmdb = _tmdb_ids(entry, query, kind)
        if _is_title_entry(entry, query, play_id):
            playable.append(entry)
            continue
        item = _folder_item(entry)
        xbmcplugin.addDirectoryItem(handle, file_url, item, False)
    status_payload = []
    parsed = []
    for entry in playable:
        query = _query(entry.get("file"))
        kind, season, episode = _kind(entry, query)
        play_id, episode_tmdb, show_tmdb = _tmdb_ids(entry, query, kind)
        parsed.append((entry, kind, season, episode, play_id, show_tmdb))
        if play_id:
            status_payload.append({
                "type": "tv" if kind in ("tv", "episode") else "movie",
                "id": _as_int(show_tmdb or play_id),
            })
    status_map = dejavu_status_map(status_payload)
    budget = 12
    for entry, kind, season, episode, play_id, show_tmdb in parsed:
        tmdb_meta, budget = enrich_tmdb(kind, show_tmdb or play_id, None, budget)
        flags = status_for(status_map, kind, play_id, show_tmdb, season, episode)
        item, play_url = _build_item(entry, tmdb_meta=tmdb_meta, flags=flags)
        xbmcplugin.addDirectoryItem(handle, play_url if play_id else (entry.get("file") or play_url), item, False)
    if capture_nav:
        _set_list_next(_wrap_directory_path(next_url) if next_url else "")
    xbmcplugin.endOfDirectory(handle, cacheToDisc=False)


def _dispatch_directory(handle, path, capture_nav=False):
    if not path:
        xbmcplugin.setContent(handle, "videos")
        xbmcplugin.endOfDirectory(handle, cacheToDisc=False)
        return
    _publish_listing(handle, _rpc_listing(path), capture_nav=capture_nav, listing_path=path)


def _is_skin_plugin(path):
    return (path or "").startswith("plugin://skin.dejavu.poc")


def _wrap_directory_path(url):
    if not url or _is_skin_plugin(url):
        return url or ""
    return "plugin://skin.dejavu.poc/?action=directory&path=%s" % quote(url, safe=":/")


def _dispatch_seeall(handle):
    path = _home_window().getProperty("dv.list.path")
    if _is_skin_plugin(path):
        params = parse_qs(urlparse(path).query)
        action = _first(params.get("action"))
        if action == "universes":
            _dispatch_universes(handle)
            _set_list_next("")
            return
        if action == "universe":
            _dispatch_universe(handle, _first(params.get("id")))
            _set_list_next("")
            return
        if action == "directory":
            _dispatch_directory(handle, unquote(_first(params.get("path")) or ""), capture_nav=True)
            return
        if action in PAGED_ACTIONS:
            media_type = _first(params.get("type"))
            page = _page_number(_first(params.get("page")))
            list_id = _first(params.get("list_id"))
            entries, next_url, from_rpc = _fetch_paged(action, media_type, page, list_id)
            _publish_listing(handle, entries, capture_nav=from_rpc)
            if not from_rpc:
                _set_list_next(next_url)
            return
        if action == "seasons":
            xbmcplugin.setContent(handle, "videos")
            tmdb_id = _first(params.get("tmdb_id"))
            if tmdb_id:
                _dispatch_seasons(handle, tmdb_id)
            _set_list_next("")
            xbmcplugin.endOfDirectory(handle, cacheToDisc=False)
            return
        if action == "episodes":
            xbmcplugin.setContent(handle, "videos")
            tmdb_id = _first(params.get("tmdb_id"))
            if tmdb_id:
                _dispatch_episodes(handle, tmdb_id, _as_int(_first(params.get("season"))) or 1)
            _set_list_next("")
            xbmcplugin.endOfDirectory(handle, cacheToDisc=False)
            return
    _dispatch_directory(handle, path, capture_nav=True)


def _end_plugin(handle):
    if handle >= 0:
        xbmcplugin.endOfDirectory(handle, succeeded=False)


def _dispatch_list_next(handle):
    nxt = _home_window().getProperty("dv.list.next")
    if nxt:
        _navigate_list(nxt, push=True)
    _end_plugin(handle)


def _dispatch_list_prev(handle):
    home = _home_window()
    prev_path = _pop_list_path(home)
    if prev_path:
        home.setProperty("dv.list.path", prev_path)
        home.clearProperty("dv.list.next")
        try:
            rev = int(home.getProperty("dv.list.rev") or 0) + 1
        except ValueError:
            rev = 1
        home.setProperty("dv.list.rev", str(rev))
        _refresh_listing()
    _end_plugin(handle)


def _dispatch_list_open(handle):
    path = _info("ListItem.Property(FolderPath)") or _info("ListItem.FileNameAndPath")
    title = _info("ListItem.Label")
    if path:
        visible = xbmc.getCondVisibility("Window.IsVisible(1116)")
        if not visible:
            home = _home_window()
            home.clearProperty("dv.list.stack")
            home.clearProperty("dv.list.prev")
            home.clearProperty("dv.list.next")
        _navigate_list(path, title=title or None, push=visible)
    _end_plugin(handle)


def _info(label):
    return xbmc.getInfoLabel(label) or ""


def _open_details(handle):
    tmdb = _info("ListItem.Property(tmdb_id)") or _info("ListItem.UniqueID(tmdb)")
    media = (_info("ListItem.Property(media_type)") or _info("ListItem.DBType") or "movie").lower()
    show = _info("ListItem.Property(tvshow_tmdb_id)")
    if show:
        tmdb = show
    if not tmdb:
        path = _info("ListItem.FileNameAndPath") or _info("ListItem.FolderPath") or _info("ListItem.Path")
        is_folder = _info("ListItem.IsFolder") == "true" or _info("ListItem.Property(IsFolder)") == "true"
        if path and is_folder:
            _navigate_list(path, title=_info("ListItem.Label") or None, push=True)
        elif path:
            xbmc.executebuiltin("PlayMedia(%s)" % path)
        else:
            xbmcgui.Dialog().notification("DejaVu", "Identifiant TMDb manquant", xbmcgui.NOTIFICATION_INFO, 3000)
        if handle >= 0:
            xbmcplugin.endOfDirectory(handle, succeeded=False)
        return
    home = xbmcgui.Window(10000)
    from lib.details import apply_details_properties, clear_details_properties
    clear_details_properties(home)
    values = {
        "dv.details.tmdb_id": tmdb,
        "dv.details.show_tmdb_id": show or tmdb,
        "dv.details.media_type": media,
        "dv.details.season": _info("ListItem.Season"),
        "dv.details.episode": _info("ListItem.Episode"),
        "dv.details.play_url": _info("ListItem.Property(play_url)") or _info("ListItem.FileNameAndPath"),
        "dv.details.percent": _info("ListItem.Property(PercentPlayed)") or _info("ListItem.PercentPlayed"),
        "dv.details.barwidth": _info("ListItem.Property(PercentBarWidth)"),
        "dv.details.title": _info("ListItem.Label"),
        "dv.details.plot": _info("ListItem.Plot"),
        "dv.details.fanart": _info("ListItem.Art(fanart)") or _info("ListItem.Art(thumb)"),
        "dv.details.poster": _info("ListItem.Art(poster)") or _info("ListItem.Icon"),
        "dv.details.status": _info("ListItem.Property(StatusLabel)"),
        "dv.details.genre": _info("ListItem.Property(GenreLabel)"),
        "dv.details.cast": _info("ListItem.Property(CastLabel)"),
        "dv.details.year": _info("ListItem.Year"),
        "dv.details.rating": _info("ListItem.Property(RatingLabel)"),
    }
    for key, value in values.items():
        home.setProperty(key, value)
    window_id = "1111" if media == "movie" else "1112"
    if media == "movie":
        try:
            apply_details_properties(tmdb, skip_lists=True)
        except Exception as exc:  # noqa: BLE001
            xbmc.log("[skin.dejavu.poc] details hydrate failed: %s" % exc, xbmc.LOGDEBUG)
    if xbmc.getCondVisibility("Window.IsVisible(%s)" % window_id):
        xbmc.executebuiltin("ReplaceWindow(%s)" % window_id, True)
    else:
        xbmc.executebuiltin("ActivateWindow(%s,,return)" % window_id, True)
    if handle >= 0:
        xbmcplugin.endOfDirectory(handle, succeeded=False)


def dispatch(argv):
    handle = int(argv[1])
    params = parse_qs(urlparse(argv[2] if len(argv) > 2 else "").query)
    action = _first(params.get("action")) or "continue_watching"
    if action not in ACTIONS:
        action = "continue_watching"
    media_type = _first(params.get("type"))
    if action == "nav_pages":
        _dispatch_nav_pages(handle)
        return
    if action == "set_page":
        from lib.pages import apply_active_page
        apply_active_page(_first(params.get("id")) or "home")
        if handle >= 0:
            xbmcplugin.endOfDirectory(handle, succeeded=False)
        return
    if action == "directory":
        _dispatch_directory(handle, unquote(_first(params.get("path")) or ""))
        return
    if action == "seeall":
        _dispatch_seeall(handle)
        return
    if action == "list_next":
        _dispatch_list_next(handle)
        return
    if action == "list_prev":
        _dispatch_list_prev(handle)
        return
    if action == "list_open":
        _dispatch_list_open(handle)
        return
    if action == "open_details":
        _open_details(handle)
        return
    if action == "details_collection":
        from lib.details import dispatch_collection
        dispatch_collection(handle, _first(params.get("tmdb_id")))
        return
    if action == "details_in_lists":
        from lib.details import dispatch_in_lists
        dispatch_in_lists(handle, _first(params.get("tmdb_id")))
        return
    if action == "details_cast":
        from lib.details import dispatch_cast
        dispatch_cast(handle, _first(params.get("tmdb_id")))
        return
    if action == "universes":
        _dispatch_universes(handle)
        return
    if action == "universe":
        _dispatch_universe(handle, _first(params.get("id")))
        return
    xbmcplugin.setContent(handle, "videos")
    if action == "seasons":
        tmdb_id = _first(params.get("tmdb_id"))
        if tmdb_id:
            _dispatch_seasons(handle, tmdb_id)
        xbmcplugin.endOfDirectory(handle, cacheToDisc=False)
        return
    if action == "episodes":
        tmdb_id = _first(params.get("tmdb_id"))
        if tmdb_id:
            _dispatch_episodes(handle, tmdb_id, _as_int(_first(params.get("season"))) or 1)
        xbmcplugin.endOfDirectory(handle, cacheToDisc=False)
        return
    if action == "details_item":
        _dispatch_details_item(handle, params)
        xbmcplugin.endOfDirectory(handle, cacheToDisc=False)
        return
    rows = _fetch_rows(action, media_type, _first(params.get("list_id")))
    playable = [entry for entry in rows if entry and not _is_more_item(entry)]
    status_payload = []
    parsed = []
    for entry in playable:
        query = _query(entry.get("file"))
        kind, season, episode = _kind(entry, query)
        play_id, episode_tmdb, show_tmdb = _tmdb_ids(entry, query, kind)
        parsed.append((entry, kind, season, episode, play_id, show_tmdb))
        if play_id:
            if kind == "episode":
                status_payload.append({
                    "type": "episode",
                    "id": _as_int(episode_tmdb or play_id),
                    "tmdbId": _as_int(show_tmdb or play_id),
                    "season": season,
                    "episode": episode,
                })
            else:
                status_payload.append({
                    "type": "tv" if kind == "tv" else "movie",
                    "id": _as_int(play_id),
                })
    status_map = dejavu_status_map(status_payload)
    budget = 12
    for entry, kind, season, episode, play_id, show_tmdb in parsed:
        meta_id = show_tmdb or play_id
        tmdb_meta, budget = enrich_tmdb(kind, meta_id, None, budget)
        flags = status_for(status_map, kind, play_id, show_tmdb, season, episode)
        item, play_url = _build_item(entry, tmdb_meta=tmdb_meta, flags=flags)
        xbmcplugin.addDirectoryItem(handle, play_url, item, False)
    xbmcplugin.endOfDirectory(handle, cacheToDisc=False)


if __name__ == "__main__":
    try:
        dispatch(sys.argv)
    except Exception as exc:  # noqa: BLE001
        xbmc.log("[skin.dejavu.poc] listings failed: %s" % exc, xbmc.LOGERROR)
        try:
            xbmcplugin.endOfDirectory(int(sys.argv[1]), succeeded=False)
        except Exception:
            pass
