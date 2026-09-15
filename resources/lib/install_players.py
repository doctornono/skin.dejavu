# -*- coding: utf-8 -*-
"""Copy bundled Alkoflix TMDb Helper players into TMDb Helper userdata."""

from __future__ import annotations

import os
import shutil
import sys

import xbmc
import xbmcaddon
import xbmcvfs


PLAYERS = (
    "alkoflix.autoplay.json",
    "alkoflix.select.json",
    "alkoflix.options.json",
)


def _translate(path):
    return xbmcvfs.translatePath(path)


def _same_file(src, dest):
    if not os.path.isfile(dest):
        return False
    try:
        if os.path.getsize(src) != os.path.getsize(dest):
            return False
        with open(src, "rb") as left, open(dest, "rb") as right:
            return left.read() == right.read()
    except OSError:
        return False


def install_players():
    skin_path = _translate(xbmcaddon.Addon("skin.dejavu.poc").getAddonInfo("path"))
    src_dir = os.path.join(skin_path, "resources", "players")
    dest_dir = os.path.join(
        _translate("special://profile/addon_data/plugin.video.themoviedb.helper"),
        "players",
    )
    if not os.path.isdir(src_dir):
        xbmc.log("[skin.dejavu.poc] bundled players folder missing", xbmc.LOGWARNING)
        return
    os.makedirs(dest_dir, exist_ok=True)
    for name in PLAYERS:
        src = os.path.join(src_dir, name)
        dest = os.path.join(dest_dir, name)
        if not os.path.isfile(src):
            continue
        if _same_file(src, dest):
            continue
        if os.path.isfile(dest) and os.path.getmtime(dest) > os.path.getmtime(src):
            continue
        shutil.copy2(src, dest)
        xbmc.log("[skin.dejavu.poc] installed TMDb Helper player %s" % name, xbmc.LOGINFO)


def main(argv=None):
    argv = list(argv if argv is not None else sys.argv)
    _lib = os.path.dirname(os.path.abspath(__file__))
    _res = os.path.dirname(_lib)
    if _res not in sys.path:
        sys.path.insert(0, _res)
    command = argv[1] if len(argv) > 1 else ""
    if command in ("apply_page", "edit_pages", "set_page", "reset_home", "watch_header", "load_details", "dejavu_action", "revalidate_cache"):
        from pages import handle_script
        handle_script(argv[1:])
        return
    try:
        install_players()
    except Exception as exc:  # noqa: BLE001 — skin startup must not crash Kodi
        xbmc.log("[skin.dejavu.poc] player install failed: %s" % exc, xbmc.LOGERROR)
    try:
        from pages import apply_active_page
        apply_active_page()
    except Exception as exc:  # noqa: BLE001
        xbmc.log("[skin.dejavu.poc] apply_page failed: %s" % exc, xbmc.LOGERROR)


if __name__ == "__main__":
    main()
