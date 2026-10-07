"""Scene 0x50 "1 2 3 スカ" (スカ = a miss) -> "1 2 3 꽝".

Scene 0x50 composes its picture from pieces (list 97:B986, see
riddle_text.py); スカ is pieces 1BA over 1BD, i.e. tiles 48/49, 58/59, 68/69,
78/79 of the asset-100 window, which no other scene shows (runtime dumps of
scenes 4F-54).  The tiles are redrawn in place: the katakana colours are
replaced from the surrounding noise, then 꽝 (Galmuri14) is drawn in red with
a dark lower-right edge like the riddle letters.  Matches message 1301.
"""
import os

import kfont
import scene_text

ASSET = 100
GRID = [[0x48, 0x49], [0x58, 0x59], [0x68, 0x69], [0x78, 0x79]]     # 16x32, rows top to bottom
ERASE = (4, 7)
STROKE, EDGE = 7, 4
TEXT, TOP, HEIGHT = '꽝', 5, 20
FONT = os.path.join(os.path.dirname(kfont.DEFAULT_BDF), 'Galmuri14.bdf')


def read(tiles):
    px = [[0] * 16 for _ in range(32)]
    for ry, row in enumerate(GRID):
        for rx, k in enumerate(row):
            t = scene_text._tile_pixels(tiles, k)
            for y in range(8):
                px[ry * 8 + y][rx * 8:rx * 8 + 8] = t[y]
    return px


def build(tiles, bdf=None):
    bdf = bdf or scene_text._font(FONT)
    px = read(tiles)
    for ry in range(4):
        for rx in range(2):
            cell = [row[rx * 8:rx * 8 + 8] for row in px[ry * 8:ry * 8 + 8]]
            clean = scene_text._erased(cell, ERASE, 9)
            for y in range(8):
                px[ry * 8 + y][rx * 8:rx * 8 + 8] = clean[y]
    g = bdf[ord(TEXT)]
    w, h, bx, by = g['bbx']
    nbits = ((w + 7) // 8) * 8
    x0 = (16 - w) // 2
    rows = [g['rows'][yy * h // HEIGHT] for yy in range(HEIGHT)]     # stretch to the digits' height
    on = {(x0 + xx, TOP + yy) for yy, row in enumerate(rows) for xx in range(w)
          if (row >> (nbits - 1 - xx)) & 1}
    for x, y in on:
        if (x + 1, y + 1) not in on and x + 1 < 16 and y + 1 < 32:
            px[y + 1][x + 1] = EDGE
    for x, y in on:
        px[y][x] = STROKE
    out = bytearray(tiles)
    for ry, row in enumerate(GRID):
        for rx, k in enumerate(row):
            out[k * 32:k * 32 + 32] = scene_text._tile_bytes([r[rx * 8:rx * 8 + 8] for r in px[ry * 8:ry * 8 + 8]])
    return bytes(out)
