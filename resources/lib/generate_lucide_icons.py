# -*- coding: utf-8 -*-
"""Rasterize bundled Lucide SVGs (ISC) into white PNGs for the skin."""

from __future__ import annotations

import math
import os
import re

from PIL import Image, ImageDraw, ImageFilter, ImageFont

# Official Lucide icon paths (ISC License, https://lucide.dev)
# viewBox 0 0 24 24, fill none, stroke, round caps/joins.
SVGS = {
    "home": (
        "M15 21v-8a1 1 0 0 0-1-1h-4a1 1 0 0 0-1 1v8",
        "M3 10a2 2 0 0 1 .709-1.528l7-5.999a2 2 0 0 1 2.582 0l7 5.999A2 2 0 0 1 21 10v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z",
    ),
    "bookmark": ("m19 21-7-4-7 4V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2v16z",),
    "sparkles": (
        "M9.937 15.5A2 2 0 0 0 8.5 14.063l-6.135-1.582a.5.5 0 0 1 0-.962L8.5 9.936A2 2 0 0 0 9.937 8.5l1.582-6.135a.5.5 0 0 1 .963 0L14.063 8.5A2 2 0 0 0 15.5 9.937l6.135 1.581a.5.5 0 0 1 0 .964L15.5 14.063a2 2 0 0 0-1.437 1.437l-1.582 6.135a.5.5 0 0 1-.963 0z",
        "M20 3v4",
        "M22 5h-4",
        "M4 17v2",
        "M5 18H3",
    ),
    "clapperboard": (
        "M20.2 6 3 11l-.9-2.4c-.3-1.1.3-2.2 1.3-2.5l13.5-4c1.1-.3 2.2.3 2.5 1.3Z",
        "m6.2 5.3 3.1 3.9",
        "m12.4 3.4 3.1 4",
        "M3 11h18v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2Z",
    ),
    "settings": (
        "M9.671 4.136a2.34 2.34 0 0 1 4.659 0 2.34 2.34 0 0 0 3.319 1.915 2.34 2.34 0 0 1 2.33 4.033 2.34 2.34 0 0 0 0 3.831 2.34 2.34 0 0 1-2.33 4.033 2.34 2.34 0 0 0-3.319 1.915 2.34 2.34 0 0 1-4.659 0 2.34 2.34 0 0 0-3.32-1.915 2.34 2.34 0 0 1-2.33-4.033 2.34 2.34 0 0 0 0-3.831A2.34 2.34 0 0 1 6.35 6.051a2.34 2.34 0 0 0 3.319-1.915",
        "M14 12a2 2 0 1 1-4 0 2 2 0 0 1 4 0",
    ),
    "refresh_cw": (
        "M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8",
        "M21 3v5h-5",
        "M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16",
        "M8 16H3v5",
    ),
    "circle_user": (
        "M18 20a6 6 0 0 0-12 0",
        "M12 14a4 4 0 1 0 0-8 4 4 0 0 0 0 8",
        "M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20",
    ),
    "power": (
        "M12 2v10",
        "M18.4 6.6a9 9 0 1 1-12.77.04",
    ),
    "tv": (
        "m17 2-5 5-5-5",
        "M4 7h16a1 1 0 0 1 1 1v12a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V8a1 1 0 0 1 1-1z",
    ),
    "music": (
        "M9 18V5l12-2v13",
        "M6 18a3 3 0 1 0 0-6 3 3 0 0 0 0 6",
        "M18 16a3 3 0 1 0 0-6 3 3 0 0 0 0 6",
    ),
    "gamepad_2": (
        "M6 11h4",
        "M8 9v4",
        "M15 12h.01",
        "M18 10h.01",
        "M17.32 5H6.68a4 4 0 0 0-3.978 3.59c-.006.052-.01.101-.017.152C2.604 9.416 2 14.456 2 16a3 3 0 0 0 3 3c1 0 1.5-.5 2-1l1.414-1.414A2 2 0 0 1 9.828 16h4.344a2 2 0 0 1 1.414.586L17 18c.5.5 1 1 2 1a3 3 0 0 0 3-3c0-1.545-.604-6.584-.685-7.258-.007-.05-.011-.1-.017-.151A4 4 0 0 0 17.32 5z",
    ),
    "layout_grid": (
        "M3 3h7v7H3z",
        "M14 3h7v7h-7z",
        "M14 14h7v7h-7z",
        "M3 14h7v7H3z",
    ),
    "image": (
        "M21 15V5a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h8",
        "m21 15-3.086-3.086a2 2 0 0 0-2.828 0L6 21",
        "M9 9a2 2 0 1 0 0-4 2 2 0 0 0 0 4",
    ),
    "folder": (
        "M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.93a2 2 0 0 1-1.66-.9l-.82-1.2A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13c0 1.1.9 2 2 2Z",
    ),
    "blocks": (
        "M10 22V8a1 1 0 0 1 1-1h10",
        "M2 17h4",
        "M6 13H2",
        "M6 21H2",
        "M10 8h11a1 1 0 0 1 1 1v12a1 1 0 0 1-1 1H11a1 1 0 0 1-1-1V8Z",
        "M6 17V3a1 1 0 0 1 1-1h4",
    ),
    "heart": (
        "M19 14c1.49-1.46 3-3.21 3-5.5A5.5 5.5 0 0 0 16.5 3c-1.76 0-3 .5-4.5 2-1.5-1.5-2.74-2-4.5-2A5.5 5.5 0 0 0 2 8.5c0 2.3 1.5 4.05 3 5.5l7 7Z",
    ),
    "cloud_sun": (
        "M12 2v2",
        "m4.93 4.93 1.41 1.41",
        "M20 12h2",
        "m19.07 4.93-1.41 1.41",
        "M15.947 12.65a4 4 0 0 0-5.925-4.128",
        "M13 22H7a5 5 0 1 1 4.9-6H13a3 3 0 0 1 0 6Z",
    ),
    "plus": ("M5 12h14", "M12 5v14"),
    "search": ("m21 21-4.34-4.34", "M11 18a7 7 0 1 0 0-14 7 7 0 0 0 0 14"),
    "list": ("M3 12h.01", "M3 18h.01", "M3 6h.01", "M8 12h13", "M8 18h13", "M8 6h13"),
    "globe": (
        "M22 12A10 10 0 1 1 2 12a10 10 0 0 1 20 0Z",
        "M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20",
        "M2 12h20",
    ),
}

SIZE = 96
PAD = 10
TOKEN = re.compile(r"[MmLlHhVvCcSsQqTtAaZz]|[-+]?(?:\d*\.\d+|\d+)(?:[eE][-+]?\d+)?")


def _nums(items):
    return [float(item) for item in items]


def _arc_to_points(x1, y1, rx, ry, phi, large, sweep, x2, y2, steps=18):
    if rx == 0 or ry == 0:
        return [(x2, y2)]
    phi = math.radians(phi)
    dx = (x1 - x2) / 2.0
    dy = (y1 - y2) / 2.0
    x1p = math.cos(phi) * dx + math.sin(phi) * dy
    y1p = -math.sin(phi) * dx + math.cos(phi) * dy
    rx, ry = abs(rx), abs(ry)
    lam = (x1p * x1p) / (rx * rx) + (y1p * y1p) / (ry * ry)
    if lam > 1:
        rx *= math.sqrt(lam)
        ry *= math.sqrt(lam)
    sign = -1 if large == sweep else 1
    num = rx * rx * ry * ry - rx * rx * y1p * y1p - ry * ry * x1p * x1p
    den = rx * rx * y1p * y1p + ry * ry * x1p * x1p
    coef = sign * math.sqrt(max(0, num / den)) if den else 0
    cxp = coef * rx * y1p / ry
    cyp = coef * -ry * x1p / rx
    cx = math.cos(phi) * cxp - math.sin(phi) * cyp + (x1 + x2) / 2
    cy = math.sin(phi) * cxp + math.cos(phi) * cyp + (y1 + y2) / 2

    def angle(ux, uy, vx, vy):
        dot = ux * vx + uy * vy
        det = ux * vy - uy * vx
        return math.copysign(math.acos(max(-1, min(1, dot / (math.hypot(ux, uy) * math.hypot(vx, vy) or 1)))), det)

    start = angle(1, 0, (x1p - cxp) / rx, (y1p - cyp) / ry)
    delta = angle((x1p - cxp) / rx, (y1p - cyp) / ry, (-x1p - cxp) / rx, (-y1p - cyp) / ry)
    if not sweep and delta > 0:
        delta -= 2 * math.pi
    if sweep and delta < 0:
        delta += 2 * math.pi
    pts = []
    for i in range(1, steps + 1):
        t = start + delta * i / steps
        x = math.cos(phi) * rx * math.cos(t) - math.sin(phi) * ry * math.sin(t) + cx
        y = math.sin(phi) * rx * math.cos(t) + math.cos(phi) * ry * math.sin(t) + cy
        pts.append((x, y))
    return pts


def _cubic(p0, p1, p2, p3, steps=12):
    pts = []
    for i in range(1, steps + 1):
        t = i / steps
        u = 1 - t
        x = u**3 * p0[0] + 3 * u**2 * t * p1[0] + 3 * u * t**2 * p2[0] + t**3 * p3[0]
        y = u**3 * p0[1] + 3 * u**2 * t * p1[1] + 3 * u * t**2 * p2[1] + t**3 * p3[1]
        pts.append((x, y))
    return pts


def path_points(d):
    tokens = TOKEN.findall(d.replace(",", " "))
    cmd = None
    i = 0
    x = y = 0.0
    sx = sy = 0.0
    cx = cy = 0.0
    points = []
    polylines = []

    def take(n):
        nonlocal i
        vals = _nums(tokens[i:i + n])
        i += n
        return vals

    while i < len(tokens):
        if tokens[i].isalpha():
            cmd = tokens[i]
            i += 1
            if cmd in "Zz":
                points.append((sx, sy))
                polylines.append(points)
                points = [(sx, sy)]
                x, y = sx, sy
                continue
        if cmd is None:
            break
        rel = cmd.islower()
        c = cmd.upper()
        if c == "M":
            mx, my = take(2)
            if rel:
                mx, my = x + mx, y + my
            if len(points) > 1:
                polylines.append(points)
            x, y = mx, my
            sx, sy = x, y
            points = [(x, y)]
            cmd = "l" if rel else "L"
        elif c == "L":
            lx, ly = take(2)
            if rel:
                lx, ly = x + lx, y + ly
            x, y = lx, ly
            points.append((x, y))
        elif c == "H":
            hx = take(1)[0]
            x = x + hx if rel else hx
            points.append((x, y))
        elif c == "V":
            vy = take(1)[0]
            y = y + vy if rel else vy
            points.append((x, y))
        elif c == "C":
            vals = take(6)
            if rel:
                vals = [x + vals[0], y + vals[1], x + vals[2], y + vals[3], x + vals[4], y + vals[5]]
            pts = _cubic((x, y), (vals[0], vals[1]), (vals[2], vals[3]), (vals[4], vals[5]))
            points.extend(pts)
            cx, cy = vals[2], vals[3]
            x, y = vals[4], vals[5]
        elif c == "S":
            vals = take(4)
            if rel:
                vals = [x + vals[0], y + vals[1], x + vals[2], y + vals[3]]
            x1, y1 = 2 * x - cx, 2 * y - cy
            pts = _cubic((x, y), (x1, y1), (vals[0], vals[1]), (vals[2], vals[3]))
            points.extend(pts)
            cx, cy = vals[0], vals[1]
            x, y = vals[2], vals[3]
        elif c == "Q":
            vals = take(4)
            if rel:
                vals = [x + vals[0], y + vals[1], x + vals[2], y + vals[3]]
            pts = _cubic((x, y), (x + 2 * (vals[0] - x) / 3, y + 2 * (vals[1] - y) / 3),
                         (vals[2] + 2 * (vals[0] - vals[2]) / 3, vals[3] + 2 * (vals[1] - vals[3]) / 3),
                         (vals[2], vals[3]))
            points.extend(pts)
            cx, cy = vals[0], vals[1]
            x, y = vals[2], vals[3]
        elif c == "A":
            rx, ry, phi, large, sweep, x2, y2 = take(7)
            if rel:
                x2, y2 = x + x2, y + y2
            points.extend(_arc_to_points(x, y, rx, ry, phi, large, sweep, x2, y2))
            x, y = x2, y2
            cx, cy = x, y
        else:
            break
    if len(points) > 1:
        polylines.append(points)
    return polylines


def render(name, paths):
    image = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    scale = (SIZE - PAD * 2) / 24.0
    width = max(3, int(round(1.75 * scale)))
    for d in paths:
        for poly in path_points(d):
            if len(poly) < 2:
                continue
            coords = [(PAD + px * scale, PAD + py * scale) for px, py in poly]
            draw.line(coords, fill=(255, 255, 255, 255), width=width, joint="curve")
            r = width / 2
            for cx, cy in (coords[0], coords[-1]):
                draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(255, 255, 255, 255))
    return image.filter(ImageFilter.GaussianBlur(0.35))


def render_logo():
    dest = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "media", "dejavu-logo-v08.png"))
    image = Image.new("RGBA", (220, 40), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    font_path = "C:/Windows/Fonts/segoeui.ttf"
    bold_path = "C:/Windows/Fonts/segoeuib.ttf"
    try:
        font = ImageFont.truetype(font_path, 26)
        bold = ImageFont.truetype(bold_path if os.path.isfile(bold_path) else font_path, 26)
    except OSError:
        font = ImageFont.load_default()
        bold = font
    draw.text((4, 4), "deja", font=font, fill=(255, 255, 255, 255))
    box = draw.textbbox((4, 4), "deja", font=font)
    draw.text((box[2] + 1, 4), "Vu", font=bold, fill=(229, 9, 20, 255))
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    image.save(dest, "PNG")
    print("wrote", dest)


def main():
    dest = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "media", "icons", "lucide"))
    os.makedirs(dest, exist_ok=True)
    for name, paths in SVGS.items():
        png = render(name, paths)
        path = os.path.join(dest, name + ".png")
        png.save(path, "PNG")
        print("wrote", path)
    render_logo()


if __name__ == "__main__":
    main()
