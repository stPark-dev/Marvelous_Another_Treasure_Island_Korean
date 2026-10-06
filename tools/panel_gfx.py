"""Korean labels for the command panel sprites (uncompressed OBJ sheet at ROM 0x2B7000).

Each 32x32 panel is four 16x16 sprites whose top-left sheet tiles are listed in
PANELS (sprite tile T uses sheet tiles T, T+1, T+16, T+17).  The label area is
x 9..28, y 4..24 of the panel; colour f is the panel face, e the letter body,
9 the letter outline.  "?!" and "EXIT" stay as they are.
"""
import os

import kfont

SHEET = 0x2B7000
# (sheet offset, face, body, outline): normal panels, then the highlighted (selected) ones
VARIANTS = [(0x2B7000, 0xF, 0xE, 0x9), (0x2B6000, 0xC, 0x2, 0xD)]
PANELS = {'team': (8, 10, 12, 14), 'item': (32, 34, 36, 38)}
LABELS = {'team': ('팀', '워크'), 'item': ('아이', '템')}
FACE, BODY, EDGE = 0xF, 0xE, 0x9
AREA = (9, 4, 28, 24)                      # inclusive x0, y0, x1, y1
SMALL_BDF = os.path.join(os.path.dirname(kfont.DEFAULT_BDF), 'Galmuri9.bdf')


def sprite_tiles(T):
    return [(T, 0, 0), (T + 1, 8, 0), (T + 16, 0, 8), (T + 17, 8, 8)]


def read_panel(rom, tiles, sheet=SHEET):
    P = [[0] * 32 for _ in range(32)]
    for T, (ox, oy) in zip(tiles, ((0, 0), (16, 0), (0, 16), (16, 16))):
        for t, dx, dy in sprite_tiles(T):
            o = sheet + t * 32
            for y in range(8):
                for x in range(8):
                    P[oy + dy + y][ox + dx + x] = sum(((rom[o + (p // 2) * 16 + 2 * y + (p & 1)] >> (7 - x)) & 1) << p
                                                      for p in range(4))
    return P


def tile_bytes(P, ox, oy):
    out = bytearray(32)
    for y in range(8):
        for x in range(8):
            c = P[oy + y][ox + x]
            for p in range(4):
                if (c >> p) & 1:
                    out[(p // 2) * 16 + 2 * y + (p & 1)] |= 0x80 >> x
    return bytes(out)


def draw_label(P, lines, bdf, face=FACE, body_c=BODY, edge=EDGE):
    x0, y0, x1, y1 = AREA
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            P[y][x] = face
    body = [[False] * 32 for _ in range(32)]
    for li, text in enumerate(lines):
        gl = [bdf[ord(ch)] for ch in text]
        width = sum(g['dw'] for g in gl) - 1
        x = x0 + (x1 - x0 + 1 - width) // 2
        top = y0 + 1 + li * 10
        for g in gl:
            w, h, bx, by = g['bbx']
            nbits = ((w + 7) // 8) * 8
            for yy, row in enumerate(g['rows']):
                for xx in range(w):
                    if (row >> (nbits - 1 - xx)) & 1:
                        body[top + (9 - by - h) + yy][x + bx + xx] = True
            x += g['dw']
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            if body[y][x]:
                P[y][x] = body_c
            elif any(body[y + dy][x + dx] for dy in (-1, 0, 1) for dx in (-1, 0, 1)):
                P[y][x] = edge
    return P


def build(rom, bdf=None):
    """Return {file offset: 32-byte tile} for every changed sheet tile."""
    bdf = bdf or kfont.load_bdf(SMALL_BDF)
    out = {}
    for sheet, face, body_c, edge in VARIANTS:
        for name, tiles in PANELS.items():
            P = draw_label(read_panel(rom, tiles, sheet), LABELS[name], bdf, face, body_c, edge)
            for T, (ox, oy) in zip(tiles, ((0, 0), (16, 0), (0, 16), (16, 16))):
                for t, dx, dy in sprite_tiles(T):
                    out[sheet + t * 32] = tile_bytes(P, ox + dx, oy + dy)
    return out
