# -*- coding: utf-8 -*-
"""Curated cinematic universes for the DejaVu home skin."""

from __future__ import annotations

import time

from lib.meta import tmdb_request
from lib.store import TMDB_TTL, get as store_get, put as store_put

IMG = "https://image.tmdb.org/t/p"


UNIVERSES = (
    {"id": "mcu", "label": "Marvel Cinematic Universe", "subtitle": "Films Marvel Studios", "company": "420"},
    {"id": "starwars", "label": "Star Wars", "subtitle": "La saga galactique", "collection": "10"},
    {"id": "dc", "label": "DC Universe", "subtitle": "Batman, Superman et plus", "company": "9993"},
    {"id": "harrypotter", "label": "Harry Potter", "subtitle": "Le monde des sorciers", "collection": "1241"},
    {"id": "lotr", "label": "Terre du Milieu", "subtitle": "Le Seigneur des Anneaux", "collection": "119"},
    {"id": "fast", "label": "Fast & Furious", "subtitle": "La famille", "collection": "9485"},
    {"id": "jurassic", "label": "Jurassic Park", "subtitle": "Le parc et le monde", "collection": "328"},
    {"id": "mission", "label": "Mission: Impossible", "subtitle": "Ethan Hunt", "collection": "87359"},
    {"id": "johnwick", "label": "John Wick", "subtitle": "Continental", "collection": "404609"},
    {"id": "matrix", "label": "Matrix", "subtitle": "Le choix d’une pilule", "collection": "2344"},
    {"id": "alien", "label": "Alien", "subtitle": "In space no one can hear you scream", "collection": "8091"},
    {"id": "xmen", "label": "X-Men", "subtitle": "Les mutants", "collection": "748"},
    {"id": "avatar", "label": "Avatar", "subtitle": "Pandora", "collection": "87096"},
    {"id": "dune", "label": "Dune", "subtitle": "Arrakis", "collection": "726871"},
    {"id": "bond", "label": "James Bond", "subtitle": "007", "collection": "645"},
    {"id": "indiana", "label": "Indiana Jones", "subtitle": "Aventures", "collection": "84"},
    {"id": "pirates", "label": "Pirates des Caraïbes", "subtitle": "Jack Sparrow", "collection": "295"},
    {"id": "transformers", "label": "Transformers", "subtitle": "Autobots et Decepticons", "collection": "91361"},
    {"id": "ghostbusters", "label": "Ghostbusters", "subtitle": "Who you gonna call?", "collection": "2980"},
    {"id": "apes", "label": "La Planète des Singes", "subtitle": "L’évolution", "collection": "173710"},
    {"id": "godzilla", "label": "Godzilla", "subtitle": "Le roi des monstres", "collection": "535313"},
    {"id": "pixar", "label": "Pixar", "subtitle": "Studios d’animation", "company": "3"},
)


def _img(path, size="w780"):
    if not path:
        return ""
    if str(path).startswith("http"):
        return str(path)
    return "%s/%s%s" % (IMG, size, path)


def _art_from_collection(collection_id):
    data = tmdb_request("collection/%s" % collection_id)
    if not data:
        return {}, data
    return {
        "poster": _img(data.get("poster_path"), "w500"),
        "fanart": _img(data.get("backdrop_path"), "w1280"),
        "thumb": _img(data.get("backdrop_path") or data.get("poster_path"), "w780"),
        "plot": data.get("overview") or "",
        "title": data.get("name") or "",
    }, data


def _art_from_company(company_id):
    movies = tmdb_request("discover/movie", {"with_companies": company_id, "sort_by": "popularity.desc"})
    results = movies.get("results") or []
    first = results[0] if results else {}
    return {
        "poster": _img(first.get("poster_path"), "w500"),
        "fanart": _img(first.get("backdrop_path"), "w1280"),
        "thumb": _img(first.get("backdrop_path") or first.get("poster_path"), "w780"),
        "plot": first.get("overview") or "",
        "title": "",
    }


def universe_card(spec, cache=None):
    cache_key = "universe:%s" % spec["id"]
    cached, age = store_get("tmdb", cache_key)
    if isinstance(cached, dict) and age is not None and age < TMDB_TTL:
        art = cached
    else:
        art = {}
        if spec.get("collection"):
            art, _data = _art_from_collection(spec["collection"])
        if (not art.get("fanart") and not art.get("poster")) and spec.get("company"):
            art = _art_from_company(spec["company"])
        art["ts"] = int(time.time())
        store_put("tmdb", cache_key, art)
        if cache is not None:
            cache[cache_key] = art
    return {
        "id": spec["id"],
        "label": spec["label"],
        "subtitle": spec.get("subtitle") or "",
        "plot": art.get("plot") or spec.get("subtitle") or "",
        "poster": art.get("poster") or "",
        "fanart": art.get("fanart") or "",
        "thumb": art.get("thumb") or art.get("fanart") or art.get("poster") or "",
    }


def _part_entry(part, media_type="movie"):
    tmdb_id = part.get("id")
    if not tmdb_id:
        return None
    title = part.get("title") or part.get("name") or ""
    poster = _img(part.get("poster_path"), "w500")
    fanart = _img(part.get("backdrop_path"), "w1280")
    year = (part.get("release_date") or part.get("first_air_date") or "")[:4]
    return {
        "filetype": "file",
        "file": "plugin://script.dejavu/?action=play&type=%s&tmdb_id=%s&title=%s" % (media_type, tmdb_id, title),
        "title": title,
        "label": title,
        "plot": part.get("overview") or "",
        "year": year,
        "fanart": fanart,
        "thumbnail": poster,
        "art": {"fanart": fanart, "poster": poster, "thumb": fanart or poster},
        "type": media_type,
        "uniqueid": {"tmdb": str(tmdb_id)},
        "resume": {"position": 0, "total": 0},
        "playcount": 0,
        "userrating": 0,
        "rating": part.get("vote_average") or 0,
        "genre": [],
        "cast": [],
    }


def _discover_entries(kind, extra):
    path = "discover/movie" if kind == "movie" else "discover/tv"
    params = {"sort_by": "popularity.desc", "page": "1"}
    params.update(extra)
    data = tmdb_request(path, params)
    entries = []
    for part in data.get("results") or []:
        entry = _part_entry(part, kind)
        if entry:
            entries.append(entry)
    return entries


def universe_entries(universe_id):
    spec = next((item for item in UNIVERSES if item["id"] == universe_id), None)
    if not spec:
        return []
    seen = set()
    rows = []

    def _add(entry):
        tmdb = (entry.get("uniqueid") or {}).get("tmdb")
        key = "%s:%s" % (entry.get("type"), tmdb)
        if not tmdb or key in seen:
            return
        seen.add(key)
        rows.append(entry)

    if spec.get("collection"):
        _art, data = _art_from_collection(spec["collection"])
        for part in data.get("parts") or []:
            entry = _part_entry(part, "movie")
            if entry:
                _add(entry)
    extra = {}
    if spec.get("company"):
        extra["with_companies"] = spec["company"]
    if spec.get("keyword"):
        extra["with_keywords"] = spec["keyword"]
    if extra:
        for entry in _discover_entries("movie", extra):
            _add(entry)
        for entry in _discover_entries("tv", extra):
            _add(entry)
    return rows
