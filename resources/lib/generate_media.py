# -*- coding: utf-8 -*-
"""Generate minimal DejaVu home textures (run from workspace, not Kodi)."""

from __future__ import annotations

import os
import struct
import zlib


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "media"))


def png(path, width, height, pixels):
    """pixels: list of (r,g,b,a) length width*height, row-major."""
    raw = bytearray()
    i = 0
    for _y in range(height):
        raw.append(0)
        for _x in range(width):
            r, g, b, a = pixels[i]
            raw.extend((r, g, b, a))
            i += 1
    comp = zlib.compress(bytes(raw), 9)

    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    data = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", comp) + chunk(b"IEND", b"")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as handle:
        handle.write(data)


def fill(w, h, color):
    return [color] * (w * h)


def rect(pixels, w, h, x0, y0, x1, y1, color):
    for y in range(max(0, y0), min(h, y1)):
        row = y * w
        for x in range(max(0, x0), min(w, x1)):
            pixels[row + x] = color


def gradient_h(w, h, left, right):
    pixels = []
    for _y in range(h):
        for x in range(w):
            t = x / max(1, w - 1)
            pixels.append(tuple(int(left[i] + (right[i] - left[i]) * t) for i in range(4)))
    return pixels


def gradient_v(w, h, top, bottom):
    pixels = []
    for y in range(h):
        t = y / max(1, h - 1)
        color = tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(4))
        pixels.extend([color] * w)
    return pixels


def circle(pixels, w, h, cx, cy, r, color):
    r2 = r * r
    for y in range(max(0, cy - r), min(h, cy + r + 1)):
        for x in range(max(0, cx - r), min(w, cx + r + 1)):
            if (x - cx) ** 2 + (y - cy) ** 2 <= r2:
                pixels[y * w + x] = color


def main():
    os.makedirs(os.path.join(ROOT, "colors"), exist_ok=True)
    white = (255, 255, 255, 255)
    black = (3, 7, 12, 255)
    red = (229, 9, 20, 255)
    dark = (20, 24, 30, 220)
    gray = (40, 46, 54, 255)
    trans = (0, 0, 0, 0)

    png(os.path.join(ROOT, "colors", "black.png"), 8, 8, fill(8, 8, (0, 0, 0, 255)))
    png(os.path.join(ROOT, "dv_header_model_v08.png"), 64, 64, fill(64, 64, (3, 7, 12, 230)))
    png(os.path.join(ROOT, "dv_button_focus_v08.png"), 32, 32, fill(32, 32, red))
    png(os.path.join(ROOT, "dv_button_v08.png"), 32, 32, fill(32, 32, gray))
    png(os.path.join(ROOT, "dv_accent_v08.png"), 8, 32, fill(8, 32, red))
    png(os.path.join(ROOT, "dv_chip_v08.png"), 32, 16, fill(32, 16, (255, 255, 255, 36)))
    png(os.path.join(ROOT, "dv_panel_v08.png"), 16, 16, fill(16, 16, (18, 22, 28, 255)))
    png(os.path.join(ROOT, "dv_progress_bg_v08.png"), 32, 8, fill(32, 8, (80, 80, 80, 200)))
    png(os.path.join(ROOT, "dv_progress_fg_v08.png"), 32, 8, fill(32, 8, red))
    png(os.path.join(ROOT, "background.jpg"), 16, 16, fill(16, 16, black))

    overlay = gradient_v(32, 80, (0, 0, 0, 0), (0, 0, 0, 200))
    png(os.path.join(ROOT, "dv_card_overlay_v08.png"), 32, 80, overlay)

    hero = []
    for y in range(200):
        vt = y / 199
        for x in range(320):
            ht = 1.0 - min(1.0, x / 180.0)
            a = int(min(230, 40 + ht * 190 + vt * 40))
            hero.append((3, 7, 12, a))
    png(os.path.join(ROOT, "hero_gradient_v08.png"), 320, 200, hero)

    focus = fill(64, 40, trans)
    rect(focus, 64, 40, 0, 0, 64, 3, red)
    rect(focus, 64, 40, 0, 37, 64, 40, red)
    rect(focus, 64, 40, 0, 0, 3, 40, red)
    rect(focus, 64, 40, 61, 0, 64, 40, red)
    png(os.path.join(ROOT, "dv_focus_v08.png"), 64, 40, focus)

    logo_path = os.path.join(ROOT, "dejavu-logo-v08.png")
    if not os.path.isfile(logo_path):
        logo = fill(130, 34, trans)
        rect(logo, 130, 34, 0, 8, 10, 26, red)
        rect(logo, 130, 34, 16, 10, 120, 24, white)
        png(logo_path, 130, 34, logo)

    def icon(name, drawer):
        pix = fill(36, 36, trans)
        drawer(pix)
        png(os.path.join(ROOT, name), 36, 36, pix)

    def house(p):
        rect(p, 36, 36, 8, 16, 28, 30, white)
        for x in range(6, 30):
            y = 16 - abs(x - 18) // 2
            rect(p, 36, 36, x, y, x + 1, 16, white)

    def film(p):
        rect(p, 36, 36, 8, 8, 28, 28, white)
        rect(p, 36, 36, 12, 12, 24, 24, trans)

    def tv(p):
        rect(p, 36, 36, 6, 10, 30, 26, white)
        rect(p, 36, 36, 10, 14, 26, 22, trans)
        rect(p, 36, 36, 16, 26, 20, 30, white)

    def bookmark(p):
        rect(p, 36, 36, 12, 6, 24, 30, white)

    def spark(p):
        rect(p, 36, 36, 17, 6, 19, 30, white)
        rect(p, 36, 36, 6, 17, 30, 19, white)

    def music(p):
        circle(p, 36, 36, 14, 26, 5, white)
        rect(p, 36, 36, 22, 8, 26, 26, white)

    def game(p):
        rect(p, 36, 36, 6, 14, 30, 24, white)

    def search(p):
        circle(p, 36, 36, 15, 15, 7, white)
        circle(p, 36, 36, 15, 15, 4, trans)
        rect(p, 36, 36, 22, 22, 30, 26, white)

    def settings(p):
        circle(p, 36, 36, 18, 18, 8, white)
        circle(p, 36, 36, 18, 18, 3, trans)

    def user(p):
        circle(p, 36, 36, 18, 12, 6, white)
        rect(p, 36, 36, 8, 22, 28, 32, white)

    def arrow(p):
        for i in range(8):
            rect(p, 36, 36, 10 + i, 12 + i, 26 - i, 13 + i, white)

    def play(p):
        for y in range(8, 28):
            span = abs(18 - y)
            rect(p, 36, 36, 12, y, 24 - span // 2, y + 1, white)

    def plus(p):
        rect(p, 36, 36, 16, 8, 20, 28, white)
        rect(p, 36, 36, 8, 16, 28, 20, white)

    def info(p):
        circle(p, 36, 36, 18, 18, 12, white)
        circle(p, 36, 36, 18, 18, 9, trans)
        rect(p, 36, 36, 17, 14, 19, 26, white)
        rect(p, 36, 36, 17, 10, 19, 12, white)

    icon("icon_home_v08.png", house)
    icon("icon_film_v08.png", film)
    icon("icon_tv_v08.png", tv)
    icon("icon_bookmark_v08.png", bookmark)
    icon("icon_spark_v08.png", spark)
    icon("icon_music_v08.png", music)
    icon("icon_game_v08.png", game)
    icon("icon_search_v08.png", search)
    icon("icon_settings_v08.png", settings)
    icon("icon_user_v08.png", user)
    icon("icon_arrow_v08.png", arrow)
    icon("icon_play_v08.png", play)
    icon("icon_plus_v08.png", plus)
    icon("icon_info_v08.png", info)

    mask = fill(84, 84, trans)
    dark = (3, 7, 12, 230)
    for y in range(84):
        for x in range(84):
            dx = x - 41.5
            dy = y - 41.5
            if dx * dx + dy * dy > 40 * 40:
                mask[y * 84 + x] = dark
    png(os.path.join(ROOT, "dv_avatar_mask_v08.png"), 84, 84, mask)
    focus_ring = fill(88, 88, trans)
    for y in range(88):
        for x in range(88):
            dx = x - 43.5
            dy = y - 43.5
            r2 = dx * dx + dy * dy
            if 40 * 40 <= r2 <= 44 * 44:
                focus_ring[y * 88 + x] = (229, 9, 20, 255)
    png(os.path.join(ROOT, "dv_avatar_focus_v08.png"), 88, 88, focus_ring)
    print("wrote textures to", ROOT)


if __name__ == "__main__":
    main()
