# -*- coding: utf-8 -*-
from generate_media import ROOT, fill, png, rect

shadow = fill(280, 158, (0, 0, 0, 0))
for y in range(158):
    for x in range(280):
        edge = min(x, y, 279 - x, 157 - y)
        alpha = 90 if edge < 8 else 40
        if edge < 18:
            shadow[y * 280 + x] = (0, 0, 0, alpha)
png("%s/dv_card_shadow_v08.png" % ROOT, 280, 158, shadow)

border = fill(280, 158, (0, 0, 0, 0))
rect(border, 280, 158, 0, 0, 280, 1, (255, 255, 255, 38))
rect(border, 280, 158, 0, 157, 280, 158, (255, 255, 255, 38))
rect(border, 280, 158, 0, 0, 1, 158, (255, 255, 255, 38))
rect(border, 280, 158, 279, 0, 280, 158, (255, 255, 255, 38))
png("%s/dv_card_border_v08.png" % ROOT, 280, 158, border)
print("card chrome written")
