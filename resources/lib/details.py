# -*- coding: utf-8 -*-
"""Movie details hydration: TMDb extras, dejaVu flags, collection and lists."""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
_RESOURCES = os.path.dirname(_LIB_DIR)
if _RESOURCES not in sys.path:
    sys.path.insert(0, _RESOURCES)
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

from lib.meta import dejavu_status_map, status_for, tmdb_request
from lib.store import TMDB_TTL, get as store_get, put as store_put


CACHE_TTL = TMDB_TTL


def _as_int(value):
    try:
        number = int(float(str(value).strip()))
    except (TypeError, ValueError):
        return 0
    return number if number > 0 else 0


def _home():
    return xbmcgui.Window(10000)


def _img(path, size="w185"):
    if not path:
        return ""
    if str(path).startswith("http"):
        return path
    return "https://image.tmdb.org/t/p/%s%s" % (size, path)


def _poster(path):
    return _img(path, "w500")


def _fanart(path):
    return _img(path, "w1280")


def _fmt_score(value, digits=1):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return ""
    if number <= 0:
        return ""
    if digits == 0:
        return str(int(round(number)))
    text = ("%%.%sf" % digits) % number
    return text.rstrip("0").rstrip(".") if "." in text else text


def _pick_trailer(videos):
    results = (videos or {}).get("results") or []
    ranked = []
    for item in results:
        if not isinstance(item, dict):
            continue
        if (item.get("site") or "") != "YouTube":
            continue
        kind = (item.get("type") or "").lower()
        key = item.get("key") or ""
        if not key:
            continue
        score = 0
        if kind == "trailer":
            score += 4
        if item.get("official"):
            score += 2
        if (item.get("iso_639_1") or "") in ("fr", "en"):
            score += 1
        ranked.append((score, key))
    if not ranked:
        return ""
    ranked.sort(reverse=True)
    return "plugin://plugin.video.youtube/play/?video_id=%s" % ranked[0][1]


def _omdb_key():
    try:
        helper = xbmcaddon.Addon("plugin.video.themoviedb.helper").getAddonInfo("path")
        resources = os.path.join(helper, "resources")
        if resources not in sys.path:
            sys.path.insert(0, resources)
        from tmdbhelper.lib.api.api_keys.omdb import API_KEY
        return API_KEY or ""
    except Exception:
        return ""


def _omdb_ratings(imdb_id):
    key = _omdb_key()
    if not key or not imdb_id:
        return {}
    url = "https://www.omdbapi.com/?%s" % urllib.parse.urlencode({"i": imdb_id, "apikey": key})
    try:
        request = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(request, timeout=8) as response:
            data = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, ValueError, TimeoutError, OSError):
        return {}
    if not isinstance(data, dict) or data.get("Response") == "False":
        return {}
    out = {}
    imdb = data.get("imdbRating")
    if imdb and imdb != "N/A":
        out["imdb"] = imdb
    meta = data.get("Metascore")
    if meta and meta != "N/A":
        out["metascore"] = meta
    for row in data.get("Ratings") or []:
        source = (row.get("Source") or "").lower()
        value = (row.get("Value") or "").strip()
        if "rotten" in source and value:
            out["rotten"] = value.split("/")[0]
        if source == "internet movie database" and value and "imdb" not in out:
            out["imdb"] = value.split("/")[0]
    return out


def fetch_movie_bundle(tmdb_id):
    cache_key = "details:movie:%s" % tmdb_id
    cached, age = store_get("tmdb", cache_key)
    if isinstance(cached, dict) and age is not None and age < CACHE_TTL:
        return cached, None, False
    data = tmdb_request(
        "movie/%s" % tmdb_id,
        {"append_to_response": "credits,videos,external_ids"},
    )
    if not data:
        return cached or {}, None, False
    genres = [g.get("name") for g in (data.get("genres") or []) if g.get("name")]
    year = (data.get("release_date") or "")[:4]
    cast_rows = []
    for person in (data.get("credits") or {}).get("cast") or []:
        name = person.get("name") or ""
        if not name:
            continue
        cast_rows.append({
            "name": name,
            "photo": _img(person.get("profile_path"), "w185"),
            "character": person.get("character") or "",
        })
        if len(cast_rows) >= 8:
            break
    collection = data.get("belongs_to_collection") or {}
    collection_id = str(collection.get("id") or "") if collection else ""
    collection_name = collection.get("name") or ""
    imdb_id = (data.get("external_ids") or {}).get("imdb_id") or data.get("imdb_id") or ""
    bundle = {
        "title": data.get("title") or data.get("original_title") or "",
        "tagline": data.get("tagline") or "",
        "plot": data.get("overview") or "",
        "year": year,
        "genre": " · ".join(genres[:3]),
        "poster": _poster(data.get("poster_path")),
        "fanart": _fanart(data.get("backdrop_path")),
        "cast": ", ".join([row["name"] for row in cast_rows[:4]]),
        "cast_rows": cast_rows,
        "collection_id": collection_id,
        "collection_name": collection_name,
        "trailer": _pick_trailer(data.get("videos")),
        "tmdb_rating": _fmt_score(data.get("vote_average")),
        "imdb_id": imdb_id,
        "ts": int(time.time()),
    }
    omdb = _omdb_ratings(imdb_id)
    bundle.update({
        "imdb_rating": omdb.get("imdb") or "",
        "metascore": omdb.get("metascore") or "",
        "rotten": omdb.get("rotten") or "",
    })
    store_put("tmdb", cache_key, bundle)
    store_put("tmdb", "movie:%s" % tmdb_id, {
        "genre": bundle.get("genre") or "",
        "year": bundle.get("year") or "",
        "cast": bundle.get("cast") or "",
        "title": bundle.get("title") or "",
        "plot": bundle.get("plot") or "",
        "poster": bundle.get("poster") or "",
        "fanart": bundle.get("fanart") or "",
        "ts": bundle.get("ts"),
    })
    return bundle, None, True


def _collection_parts(collection_id):
    data = tmdb_request("collection/%s" % collection_id)
    rows = []
    for part in (data or {}).get("parts") or []:
        tmdb_id = part.get("id")
        title = part.get("title") or part.get("name") or ""
        if not tmdb_id or not title:
            continue
        year = (part.get("release_date") or "")[:4]
        rows.append({
            "tmdb_id": str(tmdb_id),
            "title": title,
            "year": year,
            "plot": part.get("overview") or "",
            "poster": _poster(part.get("poster_path")),
            "fanart": _fanart(part.get("backdrop_path")),
            "sort": part.get("release_date") or "9999",
        })
    rows.sort(key=lambda item: item["sort"])
    return rows


def _dbg(hypothesis_id, location, message, data):
    # #region agent log
    try:
        with open(os.path.join(os.path.dirname(_RESOURCES), "debug-4ca13f.log"), "a", encoding="utf-8") as handle:
            handle.write(json.dumps({
                "sessionId": "4ca13f",
                "runId": "post-fix",
                "hypothesisId": hypothesis_id,
                "location": location,
                "message": message,
                "data": data,
                "timestamp": int(time.time() * 1000),
            }) + "\n")
    except Exception:
        pass
    # #endregion


def _row_tmdb(item):
    if not isinstance(item, dict):
        return ""
    info = item.get("info") if isinstance(item.get("info"), dict) else {}
    unique = item.get("uniqueid") if isinstance(item.get("uniqueid"), dict) else {}
    media = item.get("media") if isinstance(item.get("media"), dict) else {}
    for value in (
        item.get("tmdbId"),
        item.get("tmdb_id"),
        info.get("tmdbId"),
        info.get("tmdb_id"),
        unique.get("tmdb"),
        media.get("tmdbId"),
        media.get("id"),
        item.get("id") if str(item.get("type") or "").lower() in ("movie", "tv", "episode", "") else "",
    ):
        if value not in (None, "") and str(value).isdigit():
            return str(value)
    return ""


def _list_contains(api, list_id, tmdb_id):
    try:
        result = api.get_list_items(list_id, page=1, page_size=100, minimal=False)
    except Exception:
        return False
    try:
        from resources.lib.pure import unwrap_data, list_rows_from_result
        rows, _pagination = list_rows_from_result(result)
        if not rows:
            data = unwrap_data(result)
            if isinstance(data, list):
                rows = data
            elif isinstance(data, dict):
                rows = data.get("items") or data.get("results") or []
    except Exception:
        data = result.get("data") if isinstance(result, dict) else result
        rows = data if isinstance(data, list) else (data.get("items") if isinstance(data, dict) else [])
    needle = str(tmdb_id)
    for item in rows or []:
        if _row_tmdb(item) == needle:
            return True
    return False


def _lists_for_movie(tmdb_id):
    try:
        addon_path = xbmcaddon.Addon("script.dejavu").getAddonInfo("path")
        lib_path = os.path.join(addon_path, "resources", "lib")
        if addon_path not in sys.path:
            sys.path.insert(0, addon_path)
        if lib_path not in sys.path:
            sys.path.insert(0, lib_path)
        from client import DejaVuClient
        from resources.lib.pure import list_rows_from_result
        from lib.meta import wrap_dejavu_client
        api = wrap_dejavu_client(DejaVuClient(timeout=20))
        result = api.get_lists(page=1, page_size=50, minimal=False)
        rows, _pagination = list_rows_from_result(result)
        _dbg("E", "details.py:_lists_for_movie", "lists fetched", {"tmdb_id": str(tmdb_id), "row_count": len(rows or []), "sample_keys": list((rows or [{}])[0].keys()) if rows else []})
    except Exception as exc:
        xbmc.log("[skin.dejavu.poc] details lists failed: %s" % exc, xbmc.LOGDEBUG)
        _dbg("E", "details.py:_lists_for_movie", "lists failed", {"error": str(exc)})
        return []
    found = []
    for raw in rows or []:
        if not isinstance(raw, dict):
            continue
        list_id = raw.get("id")
        name = raw.get("name") or (raw.get("info") or {}).get("title") or ""
        if not list_id or not name:
            continue
        if _list_contains(api, list_id, tmdb_id):
            found.append({
                "id": str(list_id),
                "name": name,
                "count": raw.get("itemsCount") or raw.get("itemCount") or "",
            })
        if len(found) >= 12:
            break
    return found


def _button_labels(flags):
    flags = flags or {}
    watched = bool(flags.get("watched"))
    count = _as_int(flags.get("rewatchCount")) or (1 if watched else 0)
    rating = flags.get("rating")
    if watched and count > 1:
        watched_label = "Vu ×%s" % count
    elif watched:
        watched_label = "Vu ×1"
    else:
        watched_label = "Marquer comme vu"
    return {
        "watched": watched_label,
        "watchlist": "Liste de suivi" if flags.get("inWatchlist") else "Ajouter au suivi",
        "collection": "Dans ma collection" if flags.get("inCollection") else "Collection",
        "favorite": "Favori" if flags.get("isFavorite") else "Favoris",
        "rate": ("★ %s" % rating) if rating else "Noter",
        "list": "Ajouter à une liste",
    }


def _set_progress(home, percent_raw, barwidth_raw=""):
    try:
        percent = int(float(str(percent_raw or "0").replace("%", "").strip() or 0))
    except (TypeError, ValueError):
        percent = 0
    if percent <= 0:
        home.setProperty("dv.details.percent", "")
        home.setProperty("dv.details.barwidth", "")
        home.setProperty("dv.details.has_progress", "")
        _dbg("D", "details.py:_set_progress", "cleared because percent<=0", {"percent_raw": percent_raw, "percent": percent})
        return 0
    width = str(max(8, min(400, int(round(400 * percent / 100.0)))))
    home.setProperty("dv.details.percent", str(percent))
    home.setProperty("dv.details.barwidth", width)
    home.setProperty("dv.details.has_progress", "true")
    return percent


def _jsonable(value, depth=0):
    if depth > 6:
        return "..."
    if isinstance(value, dict):
        return {str(key): _jsonable(val, depth + 1) for key, val in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item, depth + 1) for item in value[:40]]
    if isinstance(value, (str, int, float, bool)) or value is None:
        text = value
        if isinstance(text, str) and len(text) > 400:
            return text[:400] + "…"
        return text
    return str(value)


def _dump_fiche(stage, payload):
    data = _jsonable(payload)
    xbmc.log("[skin.dejavu.poc] FICHE %s %s" % (stage, json.dumps(data, ensure_ascii=False, default=str)), xbmc.LOGINFO)
    props = payload.get("window_properties") or {}
    _dbg("F", "details.py:_dump_fiche", stage, {
        "tmdb_id": payload.get("tmdb_id"),
        "skip_lists": payload.get("skip_lists"),
        "has_progress": props.get("dv.details.has_progress"),
        "percent": props.get("dv.details.percent"),
        "cast_count": len(payload.get("tmdb_cast") or []),
        "status_map_n": len(payload.get("dejavu_status_map") or {}),
    })


DETAILS_PROPERTIES = (
    "dv.details.tmdb_id",
    "dv.details.show_tmdb_id",
    "dv.details.media_type",
    "dv.details.season",
    "dv.details.episode",
    "dv.details.play_url",
    "dv.details.percent",
    "dv.details.barwidth",
    "dv.details.has_progress",
    "dv.details.title",
    "dv.details.plot",
    "dv.details.fanart",
    "dv.details.poster",
    "dv.details.status",
    "dv.details.genre",
    "dv.details.cast",
    "dv.details.year",
    "dv.details.rating",
    "dv.details.tagline",
    "dv.details.trailer",
    "dv.details.collection_id",
    "dv.details.collection_name",
    "dv.details.has_lists",
    "dv.details.has_collection",
    "dv.details.rating_dejavu",
    "dv.details.rating_tmdb",
    "dv.details.rating_imdb",
    "dv.details.rating_metascore",
    "dv.details.rating_rotten",
    "dv.details.rating.dejavu",
    "dv.details.rating.tmdb",
    "dv.details.rating.imdb",
    "dv.details.rating.metascore",
    "dv.details.rating.rotten",
    "dv.details.btn.watched",
    "dv.details.btn.watchlist",
    "dv.details.btn.collection",
    "dv.details.btn.favorite",
    "dv.details.btn.rate",
    "dv.details.btn.list",
    "dv.details.changed",
)


def clear_details_properties(home=None):
    home = home or _home()
    for key in DETAILS_PROPERTIES:
        home.clearProperty(key)


def apply_details_properties(tmdb_id=None, skip_lists=False):
    home = _home()
    tmdb_id = str(tmdb_id or home.getProperty("dv.details.tmdb_id") or "")
    if not tmdb_id:
        return
    percent_in = home.getProperty("dv.details.percent")
    play_url = home.getProperty("dv.details.play_url")
    media_type = home.getProperty("dv.details.media_type") or "movie"
    season = home.getProperty("dv.details.season")
    episode = home.getProperty("dv.details.episode")
    show_id = home.getProperty("dv.details.show_tmdb_id")
    bundle, _cache, _dirty = fetch_movie_bundle(tmdb_id)
    status_payload = [{"type": "movie", "id": _as_int(tmdb_id)}]
    status_map = dejavu_status_map(status_payload)
    flags = status_for(status_map, "movie", tmdb_id)
    labels = _button_labels(flags)
    user_rating = flags.get("rating") or ""
    if flags:
        from lib.meta import status_label
        status_text = status_label(flags, rating_fallback=user_rating)
    else:
        status_text = ""
    values = {
        "dv.details.tmdb_id": tmdb_id,
        "dv.details.show_tmdb_id": show_id or tmdb_id,
        "dv.details.media_type": media_type,
        "dv.details.season": season,
        "dv.details.episode": episode,
        "dv.details.play_url": play_url,
        "dv.details.title": bundle.get("title") or "",
        "dv.details.tagline": bundle.get("tagline") or "",
        "dv.details.plot": bundle.get("plot") or "",
        "dv.details.year": bundle.get("year") or "",
        "dv.details.genre": bundle.get("genre") or "",
        "dv.details.cast": bundle.get("cast") or "",
        "dv.details.fanart": bundle.get("fanart") or "",
        "dv.details.poster": bundle.get("poster") or "",
        "dv.details.trailer": bundle.get("trailer") or "",
        "dv.details.collection_id": bundle.get("collection_id") or "",
        "dv.details.collection_name": bundle.get("collection_name") or "",
        "dv.details.rating_dejavu": str(user_rating) if user_rating else "",
        "dv.details.rating_tmdb": bundle.get("tmdb_rating") or "",
        "dv.details.rating_imdb": bundle.get("imdb_rating") or "",
        "dv.details.rating_metascore": bundle.get("metascore") or "",
        "dv.details.rating_rotten": bundle.get("rotten") or "",
        "dv.details.btn.watched": labels["watched"],
        "dv.details.btn.watchlist": labels["watchlist"],
        "dv.details.btn.collection": labels["collection"],
        "dv.details.btn.favorite": labels["favorite"],
        "dv.details.btn.rate": labels["rate"],
        "dv.details.btn.list": labels["list"],
        "dv.details.has_collection": "true" if bundle.get("collection_id") else "",
        "dv.details.status": status_text,
    }
    for key, value in values.items():
        home.setProperty(key, str(value or ""))
    flag_progress = flags.get("progress") if flags else None
    flag_duration = flags.get("duration") if flags else None
    progress_raw = percent_in
    if flag_progress not in (None, "", 0, "0") and flag_duration:
        try:
            progress_raw = str(max(1, min(99, int(round(100.0 * float(flag_progress) / float(flag_duration))))))
        except (TypeError, ValueError):
            pass
    percent_set = _set_progress(home, progress_raw)
    _dbg("D", "details.py:apply_details_properties", "progress", {
        "raw": progress_raw,
        "percent_set": percent_set,
        "has_progress": home.getProperty("dv.details.has_progress"),
        "barwidth": home.getProperty("dv.details.barwidth"),
        "flag_progress": flag_progress,
    })
    lists = [] if skip_lists else _lists_for_movie(tmdb_id)
    if skip_lists:
        home.setProperty("dv.details.has_lists", "")
    else:
        home.setProperty("dv.details.has_lists", "true" if lists else "")
        _dbg("E", "details.py:apply_details_properties", "lists result", {"count": len(lists), "names": [row.get("name") for row in lists]})
    home.setProperty("dv.details.changed", str(int(time.time() * 1000)))
    window_props = {}
    for key in (
        list(values.keys())
        + [
            "dv.details.percent",
            "dv.details.barwidth",
            "dv.details.has_progress",
            "dv.details.has_lists",
            "dv.details.changed",
        ]
    ):
        window_props[key] = home.getProperty(key)
    _dump_fiche("movie_details", {
        "tmdb_id": tmdb_id,
        "skip_lists": skip_lists,
        "window_properties": window_props,
        "dejavu_status_map": status_map,
        "dejavu_flags": flags,
        "tmdb_bundle": {k: v for k, v in bundle.items() if k != "cast_rows"},
        "tmdb_cast": bundle.get("cast_rows") or [],
        "lists": lists if not skip_lists else "skipped",
    })


def _movie_item(title, tmdb_id, poster, fanart, plot="", year=""):
    item = xbmcgui.ListItem(label=title, offscreen=True)
    info = {"title": title, "mediatype": "movie", "plot": plot or ""}
    if year:
        try:
            info["year"] = int(year)
        except (TypeError, ValueError):
            pass
    item.setInfo("video", info)
    item.setArt({"poster": poster, "thumb": poster, "fanart": fanart, "icon": poster})
    item.setProperty("tmdb_id", str(tmdb_id))
    item.setProperty("TmdbId", str(tmdb_id))
    item.setProperty("media_type", "movie")
    item.setProperty("DBType", "movie")
    play_url = "plugin://plugin.video.alkoflix/?%s" % urllib.parse.urlencode({
        "mode": "tmdbh_select",
        "media_type": "movie",
        "tmdb_id": tmdb_id,
        "query": title,
        "title": title,
        "autoplay": "false",
    })
    item.setProperty("play_url", play_url)
    try:
        item.setUniqueIDs({"tmdb": str(tmdb_id)}, "tmdb")
    except Exception:
        pass
    return item, play_url


def dispatch_collection(handle, tmdb_id):
    home = _home()
    collection_id = home.getProperty("dv.details.collection_id")
    if not collection_id:
        bundle, _cache, _dirty = fetch_movie_bundle(tmdb_id)
        collection_id = bundle.get("collection_id") or ""
    if not collection_id:
        xbmcplugin.endOfDirectory(handle, succeeded=True)
        return
    for row in _collection_parts(collection_id):
        item, play_url = _movie_item(row["title"], row["tmdb_id"], row["poster"], row["fanart"], row["plot"], row["year"])
        xbmcplugin.addDirectoryItem(handle, play_url, item, False)
    xbmcplugin.endOfDirectory(handle, cacheToDisc=False)


def dispatch_in_lists(handle, tmdb_id):
    for row in _lists_for_movie(tmdb_id):
        item = xbmcgui.ListItem(label=row["name"], offscreen=True)
        item.setInfo("video", {"title": row["name"], "mediatype": "set"})
        icon = "icon_bookmark_v08.png"
        item.setArt({"icon": icon, "thumb": icon, "poster": icon, "fanart": icon})
        item.setProperty("IsFolder", "true")
        item.setProperty("list_id", row["id"])
        path = "plugin://skin.dejavu.poc/?action=list_items&list_id=%s" % row["id"]
        item.setProperty("FolderPath", path)
        item.setProperty("play_url", path)
        count = row.get("count")
        if count:
            item.setProperty("SubtitleLabel", "%s titres" % count)
        xbmcplugin.addDirectoryItem(handle, path, item, True)
    xbmcplugin.endOfDirectory(handle, cacheToDisc=False)


def dispatch_cast(handle, tmdb_id):
    bundle, _cache, _dirty = fetch_movie_bundle(tmdb_id)
    rows = bundle.get("cast_rows") or []
    for index, row in enumerate(rows):
        item = xbmcgui.ListItem(label=row["name"], offscreen=True)
        photo = row.get("photo") or "icon_user_v08.png"
        item.setArt({"thumb": photo, "icon": photo, "poster": photo})
        item.setProperty("character", row.get("character") or "")
        path = "plugin://skin.dejavu.poc/?action=details_cast&tmdb_id=%s&i=%s" % (tmdb_id, index)
        xbmcplugin.addDirectoryItem(handle, path, item, False)
    _dbg("E", "details.py:dispatch_cast", "cast items", {"tmdb_id": tmdb_id, "count": len(rows)})
    xbmcplugin.endOfDirectory(handle, cacheToDisc=False)


def _details_info():
    home = _home()
    tmdb = home.getProperty("dv.details.tmdb_id")
    return {
        "dbtype": "movie",
        "api_type": "movie",
        "history_type": "movie",
        "tmdb_id": tmdb,
        "imdb_id": "",
        "show_tmdb_id": "",
        "season": None,
        "episode": None,
        "dbid": "",
        "title": home.getProperty("dv.details.title"),
        "year": home.getProperty("dv.details.year"),
        "s_cat": "",
        "playcount": None,
    }


def run_details_action(action):
    info = _details_info()
    _dbg("A", "details.py:run_details_action", "invoke", {"action": action, "tmdb_id": info.get("tmdb_id")})
    addon_path = xbmcaddon.Addon("script.dejavu").getAddonInfo("path")
    if addon_path not in sys.path:
        sys.path.insert(0, addon_path)
    import importlib.util
    spec = importlib.util.spec_from_file_location("dejavu_default", os.path.join(addon_path, "default.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    from resources.lib.api_client import DejaVuAPI
    api = DejaVuAPI()
    handlers = {
        "toggle_watched": module.toggle_watched,
        "toggle_watchlist": module.toggle_watchlist,
        "toggle_favorites": module.toggle_favorites,
        "toggle_collection": module.toggle_collection,
        "rate": module.rate_dialog,
        "add_to_list": module.add_to_list_dialog,
    }
    handler = handlers.get(action)
    if not handler:
        return
    try:
        handler(api, info)
    except Exception as exc:
        xbmc.log("[skin.dejavu.poc] details action %s failed: %s" % (action, exc), xbmc.LOGERROR)
        xbmcgui.Dialog().notification("dejaVu", "Action impossible", xbmcgui.NOTIFICATION_ERROR, 3000)
        return False

    from lib.store import invalidate_user_data, refresh_home_lists
    invalidate_user_data()
    apply_details_properties()
    _home().setProperty("dv.details.changed", str(int(time.time())))
    refresh_home_lists()
    return True


def load_details_script():
    apply_details_properties()
