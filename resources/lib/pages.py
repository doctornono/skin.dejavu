# -*- coding: utf-8 -*-
"""User-editable Home pages and widget catalog."""

from __future__ import annotations

import json
import os
import sys
import uuid

import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs

from lib.meta import execute_jsonrpc


MAX_RAILS = 8
MAX_PAGE_SLOTS = 4
RAIL_IDS = tuple(range(111, 111 + MAX_RAILS))
PLUGIN = "plugin://skin.dejavu.poc/"
DEJAVU = "plugin://script.dejavu/"

DEJAVU_FAMILIES = (
    {
        "label": "En cours",
        "id": "progress",
        "widgets": (
            {"label": "Continuer à regarder", "action": "continue_watching", "type": "", "limit": 6},
            {"label": "Scrobbles films", "action": "active_movie_scrobbles", "type": "", "limit": 6},
            {"label": "Scrobbles séries", "action": "active_tv_scrobbles", "type": "", "limit": 6},
            {"label": "Scrobbles (tous)", "action": "scrobbles", "type": "", "limit": 6},
            {"label": "À voir ensuite", "action": "up_next", "type": "", "limit": 6},
        ),
    },
    {
        "label": "Watchlist",
        "id": "watchlist",
        "widgets": (
            {"label": "Ma watchlist", "action": "watchlist", "type": "", "limit": 20},
            {"label": "Watchlist films", "action": "watchlist", "type": "movie", "limit": 20},
            {"label": "Watchlist séries", "action": "watchlist", "type": "tv", "limit": 20},
            {"label": "Ma liste · Ajouts récents", "action": "recent_watchlist", "type": "", "limit": 6},
        ),
    },
    {
        "label": "Historique",
        "id": "history",
        "widgets": (
            {"label": "Historique films", "action": "history", "type": "movie", "limit": 20},
            {"label": "Historique séries", "action": "history", "type": "tv", "limit": 20},
            {"label": "Historique épisodes", "action": "history", "type": "episode", "limit": 20},
        ),
    },
    {
        "label": "Favoris",
        "id": "favorites",
        "widgets": (
            {"label": "Favoris", "action": "favorites", "type": "", "limit": 20},
            {"label": "Favoris films", "action": "favorites", "type": "movie", "limit": 20},
            {"label": "Favoris séries", "action": "favorites", "type": "tv", "limit": 20},
        ),
    },
    {
        "label": "Notes",
        "id": "ratings",
        "widgets": (
            {"label": "Notes", "action": "ratings", "type": "", "limit": 20},
            {"label": "Notes films", "action": "ratings", "type": "movie", "limit": 20},
            {"label": "Notes séries", "action": "ratings", "type": "tv", "limit": 20},
            {"label": "Notes épisodes", "action": "ratings", "type": "episode", "limit": 20},
        ),
    },
    {
        "label": "Collection",
        "id": "collection",
        "widgets": (
            {"label": "Collection", "action": "collection", "type": "", "limit": 20},
            {"label": "Collection films", "action": "collection", "type": "movie", "limit": 20},
            {"label": "Collection séries", "action": "collection", "type": "tv", "limit": 20},
        ),
    },
    {
        "label": "Sorties",
        "id": "upcoming",
        "widgets": (
            {"label": "Films à venir", "action": "upcoming_releases", "type": "", "limit": 20},
            {"label": "Planning séries", "action": "upcoming_schedule", "type": "", "limit": 20},
        ),
    },
)

DEJAVU_PLOTS = {
    "continue_watching": "Reprendre les films et séries en cours.",
    "active_movie_scrobbles": "Lectures de films en cours.",
    "active_tv_scrobbles": "Lectures de séries en cours.",
    "scrobbles": "Toutes les lectures en cours.",
    "up_next": "Les prochains épisodes et titres à enchaîner.",
    "recent_watchlist": "Les ajouts les plus récents à votre liste.",
    "watchlist": "Tous les titres enregistrés dans votre watchlist.",
    "history": "Les titres récemment regardés.",
    "favorites": "Vos titres favoris.",
    "ratings": "Les titres que vous avez notés.",
    "collection": "Votre collection.",
    "upcoming_releases": "Les films bientôt disponibles.",
    "upcoming_schedule": "Les prochaines sorties de séries.",
    "list_items": "Une de vos listes personnelles.",
}

LIBRARY_MOVIE_VIEWS = (
    {"label": "Tous les films", "view": "titles", "path": "videodb://movies/titles/"},
    {"label": "Films récemment ajoutés", "view": "recent", "path": "videodb://recentlyaddedmovies/"},
    {"label": "Films en cours", "view": "inprogress", "path": "videodb://inprogressmovies/"},
)

LIBRARY_TV_VIEWS = (
    {"label": "Toutes les séries", "view": "titles", "path": "videodb://tvshows/titles/"},
    {"label": "Épisodes récemment ajoutés", "view": "recent", "path": "videodb://recentlyaddedepisodes/"},
    {"label": "Séries en cours", "view": "inprogress", "path": "videodb://inprogresstvshows/"},
)


def _addon():
    return xbmcaddon.Addon("skin.dejavu.poc")


def _pages_path():
    profile = xbmcvfs.translatePath("special://profile/addon_data/skin.dejavu.poc")
    os.makedirs(profile, exist_ok=True)
    return os.path.join(profile, "pages.json")


def _defaults_path():
    return os.path.join(_addon().getAddonInfo("path"), "resources", "defaults", "pages.json")


def default_data():
    path = _defaults_path()
    if os.path.isfile(path):
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    return {
        "version": 1,
        "active_page": "home",
        "pages": [{"id": "home", "label": "Accueil", "builtin": True, "in_header": True, "rails": []}],
    }


def load_data():
    path = _pages_path()
    if not os.path.isfile(path):
        data = default_data()
        save_data(data)
        return data
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        data = default_data()
        save_data(data)
        return data
    if not isinstance(data.get("pages"), list) or not data["pages"]:
        data = default_data()
        save_data(data)
        return data
    _ensure_builtin_pages(data)
    return data


def _ensure_builtin_pages(data):
    existing = {page.get("id") for page in data.get("pages") or []}
    changed = False
    for page in default_data().get("pages") or []:
        if page.get("id") and page.get("id") not in existing:
            data.setdefault("pages", []).append(page)
            changed = True
    if changed:
        save_data(data)


def save_data(data):
    path = _pages_path()
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)


def _page_by_id(data, page_id):
    for page in data.get("pages") or []:
        if page.get("id") == page_id:
            return page
    return (data.get("pages") or [None])[0]


def rail_urls(rail):
    source = rail.get("source") or "dejavu"
    limit = int(rail.get("limit") or 12)
    if source == "dejavu":
        action = rail.get("action") or "watchlist"
        media = rail.get("type") or ""
        query = "action=%s" % action
        if media:
            query += "&type=%s" % media
        list_id = rail.get("list_id") or ""
        if list_id:
            query += "&list_id=%s" % list_id
        content = "%s?%s" % (PLUGIN.rstrip("/"), query)
        seeall = content
        if action == "recent_watchlist":
            seeall = "%s?action=watchlist" % PLUGIN.rstrip("/")
        return content, seeall, str(limit)
    if source == "universes":
        content = "%s?action=universes" % PLUGIN.rstrip("/")
        return content, content, str(limit)
    path = rail.get("path") or ""
    if source == "library":
        path = path or _library_path(rail.get("media") or "movies", rail.get("view") or "titles")
    content = "%s?action=directory&path=%s" % (PLUGIN.rstrip("/"), _quote(path))
    return content, content, str(limit)


def _quote(value):
    from urllib.parse import quote

    # Encode query separators so nested plugin URLs stay a single `path=` value.
    return quote(value or "", safe=":/")


def _library_path(media, view):
    views = LIBRARY_MOVIE_VIEWS if media == "movies" else LIBRARY_TV_VIEWS
    for item in views:
        if item["view"] == view:
            return item["path"]
    return views[0]["path"]


def apply_active_page(page_id=None, persist=True, steal_focus=False):
    data = load_data()
    if page_id:
        if persist and data.get("active_page") != page_id:
            data["active_page"] = page_id
            save_data(data)
        elif not persist:
            data["active_page"] = page_id
    page = _page_by_id(data, data.get("active_page") or "home")
    if not page:
        return
    home = xbmcgui.Window(10000)
    rails = list(page.get("rails") or [])[:MAX_RAILS]
    page_key = page.get("id") or "home"
    signature = _page_signature(rails)
    cache_slot = _find_cache_slot(home, page_key)
    must_load = True
    if cache_slot is None:
        cache_slot = _allocate_cache_slot(home, page_key)
    elif home.getProperty("dv.cache.%s.sig" % cache_slot) == signature:
        must_load = False
    if must_load:
        _bind_page_slot(home, cache_slot, page_key, signature, rails, refresh=True)
    home.setProperty("dv.page.id", page_key)
    home.setProperty("dv.page.label", page.get("label") or "Accueil")
    home.setProperty("dv.active.slot", str(cache_slot))
    first_list = str(_slot_list_ids(cache_slot)[0])
    home.setProperty("dv.focus.rail", first_list)
    saved_hero = home.getProperty("dv.cache.%s.hero" % cache_slot)
    home.setProperty("dv.hero.rail", saved_hero or first_list)
    _sync_hero(home, saved_hero or first_list)
    _touch_cache_lru(home, cache_slot)
    if steal_focus and xbmc.getCondVisibility("Window.IsVisible(Home)"):
        xbmc.executebuiltin("SetFocus(%s)" % first_list)


def _page_signature(rails):
    parts = []
    for rail in rails:
        content, _seeall, limit = rail_urls(rail)
        parts.append("%s#%s" % (content, limit))
    return "|".join(parts)


def _slot_list_ids(cache_slot):
    base = 111 + cache_slot * 100
    return tuple(range(base, base + MAX_RAILS))


def _find_cache_slot(home, page_key):
    for index in range(MAX_PAGE_SLOTS):
        if home.getProperty("dv.cache.%s.page" % index) == page_key:
            return index
    return None


def _allocate_cache_slot(home, page_key=""):
    home_locked = home.getProperty("dv.cache.0.page") == "home"
    if page_key == "home":
        occupant = home.getProperty("dv.cache.0.page")
        if not occupant or occupant == "home":
            return 0
    for index in range(MAX_PAGE_SLOTS):
        if home_locked and index == 0 and page_key != "home":
            continue
        if not home.getProperty("dv.cache.%s.page" % index):
            return index
    order = [item for item in (home.getProperty("dv.cache.lru") or "").split(",") if item != ""]
    for item in order:
        try:
            index = int(item)
        except ValueError:
            continue
        if home_locked and index == 0 and page_key != "home":
            continue
        return index
    return 1 if home_locked and page_key != "home" else 0


def _touch_cache_lru(home, cache_slot):
    current = str(cache_slot)
    order = [item for item in (home.getProperty("dv.cache.lru") or "").split(",") if item and item != current]
    order.append(current)
    home.setProperty("dv.cache.lru", ",".join(order))


def _addon_id_from_path(path):
    raw = (path or "").strip()
    if raw.startswith("plugin://"):
        raw = raw[9:]
    elif raw.startswith("addons://"):
        raw = raw.split("/", 2)[-1] if "/" in raw else raw
    return raw.split("/")[0].split("?")[0]


def _first_directory_art(path):
    if not path:
        return "", "", ""
    result = _rpc("Files.GetDirectory", {
        "directory": path,
        "media": "video",
        "properties": ["fanart", "thumbnail", "art", "plot"],
        "limits": {"start": 0, "end": 1},
    })
    files = result.get("files") or []
    if not files:
        return "", "", ""
    entry = files[0]
    art = entry.get("art") or {}
    fanart = art.get("fanart") or entry.get("fanart") or ""
    poster = art.get("poster") or art.get("thumb") or entry.get("thumbnail") or ""
    return fanart, poster, entry.get("plot") or ""


def _rail_hero(rail):
    source = rail.get("source") or "dejavu"
    title = rail.get("title") or "Rail"
    plot = fanart = poster = ""
    if source == "addon":
        addon_id = _addon_id_from_path(rail.get("path") or "")
        if addon_id:
            try:
                addon = xbmcaddon.Addon(addon_id)
                plot = addon.getAddonInfo("description") or ""
                fanart = addon.getAddonInfo("fanart") or ""
                poster = addon.getAddonInfo("icon") or ""
            except Exception:
                pass
    elif source == "library":
        media = rail.get("media") or "movies"
        views = LIBRARY_MOVIE_VIEWS if media == "movies" else LIBRARY_TV_VIEWS
        view_label = title
        for item in views:
            if item["view"] == rail.get("view"):
                view_label = item["label"]
                break
        path = rail.get("path") or _library_path(media, rail.get("view") or "titles")
        fanart, poster, item_plot = _first_directory_art(path)
        plot = item_plot or view_label
    elif source == "universes":
        plot = "Univers cinématographiques et collections liées."
    else:
        plot = DEJAVU_PLOTS.get(rail.get("action") or "", title)
    return plot, fanart, poster, source


def _bind_page_slot(home, cache_slot, page_key, signature, rails, refresh):
    list_ids = _slot_list_ids(cache_slot)
    for index in range(MAX_RAILS):
        rail_no = index + 1
        title = content = seeall = limit = plot = fanart = poster = source = ""
        if index < len(rails):
            title = rails[index].get("title") or "Rail"
            content, seeall, limit = rail_urls(rails[index])
            plot, fanart, poster, source = _rail_hero(rails[index])
        prefix = "dv.s%s.r%s." % (cache_slot, rail_no)
        home.setProperty(prefix + "title", title)
        home.setProperty(prefix + "content", content)
        home.setProperty(prefix + "seeall", seeall)
        home.setProperty(prefix + "limit", limit or "12")
        home.setProperty(prefix + "list", str(list_ids[index]))
        home.setProperty(prefix + "plot", plot)
        home.setProperty(prefix + "fanart", fanart)
        home.setProperty(prefix + "poster", poster)
        home.setProperty(prefix + "source", source)
        home.setProperty("dv.rail.%s.title" % rail_no, title)
        home.setProperty("dv.rail.%s.content" % rail_no, content)
        home.setProperty("dv.rail.%s.seeall" % rail_no, seeall)
        home.setProperty("dv.rail.%s.limit" % rail_no, limit or "12")
        home.setProperty("dv.rail.%s.list" % rail_no, str(list_ids[index]))
    home.setProperty("dv.cache.%s.page" % cache_slot, page_key)
    home.setProperty("dv.cache.%s.sig" % cache_slot, signature)
    if refresh and xbmc.getCondVisibility("Window.IsVisible(Home)"):
        for list_id in list_ids:
            xbmc.executebuiltin("Container(%s).Refresh" % list_id)


def _sync_hero(home, list_id):
    item = "Container(%s).ListItem." % list_id
    fanart = xbmc.getInfoLabel(item + "Art(fanart)") or xbmc.getInfoLabel(item + "Art(thumb)")
    home.setProperty("dv.hero.mode", "item")
    home.clearProperty("dv.hero.poster")
    home.clearProperty("dv.hero.source")
    home.clearProperty("dv.hero.itemfanart")
    home.clearProperty("dv.hero.itemposter")
    home.setProperty("dv.hero.fanart", fanart or "")
    home.setProperty("dv.hero.thumb", xbmc.getInfoLabel(item + "Art(thumb)") or "")
    home.setProperty("dv.hero.label", xbmc.getInfoLabel(item + "Label") or "")
    home.setProperty("dv.hero.plot", xbmc.getInfoLabel(item + "Plot") or "")
    home.setProperty("dv.hero.year", xbmc.getInfoLabel(item + "Year") or "")
    home.setProperty("dv.hero.genre", xbmc.getInfoLabel(item + "Property(GenreLabel)") or "")
    home.setProperty("dv.hero.cast", xbmc.getInfoLabel(item + "Property(CastLabel)") or "")
    home.setProperty("dv.hero.status", xbmc.getInfoLabel(item + "Property(StatusLabel)") or "")
    home.setProperty("dv.hero.rating", xbmc.getInfoLabel(item + "Property(RatingLabel)") or "")
    home.setProperty("dv.hero.barwidth", xbmc.getInfoLabel(item + "Property(PercentBarWidth)") or "0")
    home.setProperty("dv.hero.play", xbmc.getInfoLabel(item + "FileNameAndPath") or "")
    home.setProperty("dv.hero.media", xbmc.getInfoLabel(item + "Property(media_type)") or "")
    home.setProperty("dv.hero.rail", str(list_id))


def nav_items():
    data = load_data()
    items = []
    for page in data.get("pages") or []:
        if page.get("in_header", True):
            items.append({
                "label": page.get("label") or page.get("id"),
                "icon": _nav_icon(page.get("id")),
                "nav_action": "RunScript(skin.dejavu.poc,set_page,%s)" % page.get("id"),
                "page_id": page.get("id") or "",
            })
    return items


def _nav_icon(page_id):
    if page_id == "home":
        return "icons/lucide/home.png"
    if page_id == "univers":
        return "icons/lucide/globe.png"
    return "icons/lucide/layout_grid.png"


def _keyboard(heading, default=""):
    keyboard = xbmc.Keyboard(default, heading)
    keyboard.doModal()
    if not keyboard.isConfirmed():
        return None
    return (keyboard.getText() or "").strip()


def _select(heading, options):
    labels = [item["label"] for item in options]
    choice = xbmcgui.Dialog().select(heading, labels)
    if choice < 0:
        return None
    return options[choice]


def _rpc(method, params):
    data = execute_jsonrpc(method, params)
    return data.get("result") or {}


def list_video_addons():
    result = _rpc("Addons.GetAddons", {
        "type": "xbmc.addon.video",
        "enabled": True,
        "properties": ["name", "thumbnail"],
    })
    addons = []
    for item in result.get("addons") or []:
        addon_id = item.get("addonid") or ""
        if addon_id in ("skin.dejavu.poc",):
            continue
        addons.append({
            "id": addon_id,
            "label": item.get("name") or addon_id,
            "path": "plugin://%s/" % addon_id,
        })
    addons.sort(key=lambda row: row["label"].lower())
    return addons


def browse_directory(path):
    result = _rpc("Files.GetDirectory", {
        "directory": path,
        "media": "files",
        "properties": ["title", "file", "thumbnail"],
    })
    rows = []
    for entry in result.get("files") or []:
        file_url = entry.get("file") or ""
        if not file_url:
            continue
        rows.append({
            "label": entry.get("label") or entry.get("title") or file_url,
            "path": file_url,
            "folder": entry.get("filetype") == "directory",
        })
    return rows


def pick_addon_path():
    addons = list_video_addons()
    if not addons:
        xbmcgui.Dialog().ok("Pages", "Aucune extension vidéo activée.")
        return None
    chosen = _select("Choisir une extension", addons)
    if not chosen:
        return None
    current = chosen["path"]
    while True:
        options = [{"label": "Utiliser ce dossier", "path": current, "use": True}]
        for row in browse_directory(current):
            suffix = "  >" if row["folder"] else ""
            options.append({
                "label": row["label"] + suffix,
                "path": row["path"],
                "folder": row["folder"],
            })
        picked = _select(current, options)
        if not picked:
            return None
        if picked.get("use"):
            return current
        if picked.get("folder"):
            current = picked["path"]
            continue
        return picked["path"]


def _dejavu_user_lists():
    try:
        addon_path = xbmcaddon.Addon("script.dejavu").getAddonInfo("path")
        lib_path = os.path.join(addon_path, "resources", "lib")
        if lib_path not in sys.path:
            sys.path.insert(0, lib_path)
        from client import DejaVuClient
        from pure import list_rows_from_result
        from lib.meta import wrap_dejavu_client

        result = wrap_dejavu_client(DejaVuClient(timeout=20)).get_lists(page=1, page_size=50, minimal=True)
        rows, _pagination = list_rows_from_result(result)
        if not rows:
            data = result.get("data") if isinstance(result, dict) else result
            if isinstance(data, dict):
                rows = data.get("lists") or data.get("data") or []
            elif isinstance(data, list):
                rows = data
        widgets = []
        for row in rows or []:
            if not isinstance(row, dict):
                continue
            list_id = row.get("id") or row.get("listId") or row.get("list_id")
            name = row.get("name") or (row.get("info") or {}).get("title") or str(list_id or "")
            if not list_id or not name:
                continue
            widgets.append({
                "label": name,
                "action": "list_items",
                "type": "",
                "list_id": str(list_id),
                "limit": 20,
            })
        return widgets
    except Exception as exc:  # noqa: BLE001
        xbmc.log("[skin.dejavu.poc] dejavu lists failed: %s" % exc, xbmc.LOGDEBUG)
        return []


def _finish_dejavu_widget(widget):
    title = _keyboard("Titre du rail", widget.get("label") or "")
    if title is None:
        return None
    rail = {
        "title": title or widget.get("label") or "DejaVu",
        "source": "dejavu",
        "action": widget.get("action") or "watchlist",
        "type": widget.get("type") or "",
        "limit": widget.get("limit") or 12,
    }
    if widget.get("list_id"):
        rail["list_id"] = widget["list_id"]
    return rail


def _pick_dejavu_widget():
    families = [{"label": item["label"], "id": item["id"]} for item in DEJAVU_FAMILIES]
    families.append({"label": "Mes listes", "id": "lists"})
    family = _select("Widget DejaVu", families)
    if not family:
        return None
    if family["id"] == "lists":
        lists = _dejavu_user_lists()
        if not lists:
            xbmcgui.Dialog().notification("DejaVu", "Aucune liste personnelle", xbmcgui.NOTIFICATION_INFO, 3000)
            return None
        widget = _select("Mes listes", lists)
        if not widget:
            return None
        return _finish_dejavu_widget(widget)
    group = next((item for item in DEJAVU_FAMILIES if item["id"] == family["id"]), None)
    if not group:
        return None
    widget = _select(group["label"], [{"label": item["label"], **item} for item in group["widgets"]])
    if not widget:
        return None
    return _finish_dejavu_widget(widget)


def _pick_widget():
    category = _select("Type de widget", (
        {"label": "DejaVu", "id": "dejavu"},
        {"label": "Bibliothèque films", "id": "movies"},
        {"label": "Bibliothèque séries", "id": "tvshows"},
        {"label": "Extension", "id": "addon"},
    ))
    if not category:
        return None
    if category["id"] == "dejavu":
        return _pick_dejavu_widget()
    if category["id"] in ("movies", "tvshows"):
        views = LIBRARY_MOVIE_VIEWS if category["id"] == "movies" else LIBRARY_TV_VIEWS
        view = _select("Vue bibliothèque", list(views))
        if not view:
            return None
        title = _keyboard("Titre du rail", view["label"])
        if title is None:
            return None
        return {
            "title": title or view["label"],
            "source": "library",
            "media": "movies" if category["id"] == "movies" else "tvshows",
            "view": view["view"],
            "path": view["path"],
            "limit": 20,
        }
    path = pick_addon_path()
    if not path:
        return None
    title = _keyboard("Titre du rail", "Extension")
    if title is None:
        return None
    return {"title": title or "Extension", "source": "addon", "path": path, "limit": 20}


def _pick_limit(current):
    options = (
        {"label": "6", "limit": 6},
        {"label": "12", "limit": 12},
        {"label": "20", "limit": 20},
    )
    picked = _select("Nombre d'éléments (actuel : %s)" % current, options)
    return picked["limit"] if picked else None


def _edit_rails(page):
    while True:
        rails = list(page.get("rails") or [])
        options = [{"label": "+ Ajouter un rail", "add": True}]
        for index, rail in enumerate(rails):
            options.append({"label": "%s. %s" % (index + 1, rail.get("title") or "Rail"), "index": index})
        picked = _select("Rails — %s" % (page.get("label") or ""), options)
        if not picked:
            return
        if picked.get("add"):
            if len(rails) >= MAX_RAILS:
                xbmcgui.Dialog().ok("Pages", "Maximum %s rails par page." % MAX_RAILS)
                continue
            rail = _pick_widget()
            if rail:
                rails.append(rail)
                page["rails"] = rails
            continue
        index = picked["index"]
        rail = rails[index]
        action = _select(rail.get("title") or "Rail", (
            {"label": "Renommer", "id": "rename"},
            {"label": "Changer le contenu", "id": "content"},
            {"label": "Limite", "id": "limit"},
            {"label": "Monter", "id": "up"},
            {"label": "Descendre", "id": "down"},
            {"label": "Supprimer", "id": "delete"},
        ))
        if not action:
            continue
        if action["id"] == "rename":
            title = _keyboard("Titre du rail", rail.get("title") or "")
            if title:
                rail["title"] = title
        elif action["id"] == "content":
            replacement = _pick_widget()
            if replacement:
                rails[index] = replacement
        elif action["id"] == "limit":
            limit = _pick_limit(rail.get("limit") or 12)
            if limit:
                rail["limit"] = limit
        elif action["id"] == "up" and index > 0:
            rails[index - 1], rails[index] = rails[index], rails[index - 1]
        elif action["id"] == "down" and index < len(rails) - 1:
            rails[index + 1], rails[index] = rails[index], rails[index + 1]
        elif action["id"] == "delete":
            if xbmcgui.Dialog().yesno("Pages", "Supprimer ce rail ?"):
                rails.pop(index)
        page["rails"] = rails


def edit_pages():
    data = load_data()
    while True:
        options = [{"label": "+ Nouvelle page", "create": True}]
        for page in data.get("pages") or []:
            mark = " •" if page.get("id") == data.get("active_page") else ""
            options.append({
                "label": "%s%s" % (page.get("label") or page.get("id"), mark),
                "id": page.get("id"),
            })
        options.append({"label": "Réinitialiser Accueil", "reset": True})
        picked = _select("Pages", options)
        if not picked:
            save_data(data)
            apply_active_page()
            return
        if picked.get("create"):
            label = _keyboard("Nom de la page", "Nouvelle page")
            if not label:
                continue
            page = {
                "id": "page-%s" % uuid.uuid4().hex[:8],
                "label": label,
                "builtin": False,
                "in_header": True,
                "rails": [],
            }
            data["pages"].append(page)
            _edit_page(data, page)
            continue
        if picked.get("reset"):
            if xbmcgui.Dialog().yesno("Pages", "Restaurer les rails par défaut d'Accueil ?"):
                defaults = default_data()
                home = _page_by_id(defaults, "home")
                current = _page_by_id(data, "home")
                if current and home:
                    current["rails"] = home.get("rails") or []
                    current["label"] = home.get("label") or "Accueil"
            continue
        page = _page_by_id(data, picked.get("id"))
        if page:
            _edit_page(data, page)


def _edit_page(data, page):
    while True:
        header = "Oui" if page.get("in_header", True) else "Non"
        options = [
            {"label": "Rails", "id": "rails"},
            {"label": "Renommer (%s)" % (page.get("label") or ""), "id": "rename"},
            {"label": "Afficher dans le header (%s)" % header, "id": "header"},
        ]
        if not page.get("builtin"):
            options.append({"label": "Supprimer la page", "id": "delete"})
        picked = _select(page.get("label") or "Page", options)
        if not picked:
            return
        if picked["id"] == "rails":
            _edit_rails(page)
        elif picked["id"] == "rename":
            label = _keyboard("Nom de la page", page.get("label") or "")
            if label:
                page["label"] = label
        elif picked["id"] == "header":
            page["in_header"] = not page.get("in_header", True)
        elif picked["id"] == "delete":
            if xbmcgui.Dialog().yesno("Pages", "Supprimer « %s » ?" % (page.get("label") or "")):
                data["pages"] = [item for item in data["pages"] if item.get("id") != page.get("id")]
                if data.get("active_page") == page.get("id"):
                    data["active_page"] = "home"
                return


def _header_nav_visible():
    return xbmc.getCondVisibility("Window.IsVisible(Home)")


def _apply_header_selection(page_id):
    apply_active_page(page_id, persist=True, steal_focus=False)


def watch_header():
    home = xbmcgui.Window(10000)
    already = home.getProperty("dv.nav.watching")
    if already == "1":
        return
    home.setProperty("dv.nav.watching", "1")
    monitor = xbmc.Monitor()
    last_page = home.getProperty("dv.page.id") or ""
    pending = ""
    pending_ticks = 0
    hidden_ticks = 0
    last_snap = None
    try:
        while not monitor.abortRequested():
            if _header_nav_visible():
                hidden_ticks = 0
            else:
                hidden_ticks += 1
                if hidden_ticks > 8:
                    break
            slot = home.getProperty("dv.active.slot") or "0"
            try:
                slot_i = int(slot)
            except ValueError:
                slot_i = 0
            rail_ids = _slot_list_ids(slot_i)
            focused = None
            if xbmc.getCondVisibility("Control.HasFocus(1001)"):
                focused = 1001
            else:
                for cid in rail_ids:
                    if xbmc.getCondVisibility("Control.HasFocus(%s)" % cid):
                        focused = cid
                        break
            pos = ""
            if focused and focused != 1001:
                pos = xbmc.getInfoLabel("Container(%s).CurrentItem" % focused) or ""
            snap = (focused, pos, slot, home.getProperty("dv.page.id"))
            if snap != last_snap:
                last_snap = snap
                if focused and focused != 1001:
                    _sync_hero(home, focused)
            if xbmc.getCondVisibility("Control.HasFocus(1001)"):
                page_id = xbmc.getInfoLabel("Container(1001).ListItem.Property(page_id)") or ""
                if page_id:
                    if page_id != pending:
                        pending = page_id
                        pending_ticks = 0
                    else:
                        pending_ticks += 1
                    if pending_ticks >= 1 and page_id != last_page:
                        last_page = page_id
                        if page_id != (home.getProperty("dv.page.id") or ""):
                            _apply_header_selection(page_id)
            if monitor.waitForAbort(0.12):
                break
    finally:
        home.clearProperty("dv.nav.watching")


def handle_script(args):
    command = args[0] if args else "apply_page"
    if command == "edit_pages":
        edit_pages()
        return
    if command == "watch_header":
        watch_header()
        return
    if command == "load_details":
        from lib.details import load_details_script
        load_details_script()
        return
    if command == "dejavu_action":
        from lib.details import run_details_action
        run_details_action(args[1] if len(args) > 1 else "")
        return
    if command == "revalidate_cache":
        try:
            from lib.listings import warm_home_rails
            from lib.store import refresh_home_lists
            data = load_data()
            page = _page_by_id(data, xbmcgui.Window(10000).getProperty("dv.page.id") or data.get("active_page") or "home")
            warm_home_rails((page or {}).get("rails") or [], force=True)
            refresh_home_lists()
        except Exception as exc:  # noqa: BLE001
            xbmc.log("[skin.dejavu.poc] revalidate failed: %s" % exc, xbmc.LOGDEBUG)
        xbmcgui.Window(10000).clearProperty("dv.cache.revalidating")
        return
    if command == "set_page":
        page_id = args[1] if len(args) > 1 else "home"
        apply_active_page(page_id, steal_focus=False)
        if not xbmc.getCondVisibility("Window.IsVisible(Home)"):
            xbmc.executebuiltin("ActivateWindow(Home)")
        return
    if command == "reset_home":
        data = load_data()
        home = _page_by_id(default_data(), "home")
        current = _page_by_id(data, "home")
        if current and home:
            current["rails"] = home.get("rails") or []
            save_data(data)
        apply_active_page("home")
        return
    apply_active_page()
