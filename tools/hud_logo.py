"""HUD status-bar logo マーヴェラス (2bpp, file 0x26A400 = 8D:A400, 128x16, two tile rows).

Letters are colour 1 filled with a colour-3 outline; the Korean logo uses
scaled Galmuri11-Bold syllables in the same style.
"""
import kfont

BASE = 0x26A400
TEXT = '마벨러스'


def scaled(ch, bdf, w, h):
    g = bdf[ord(ch)]
    gw, gh, bx, by = g['bbx']
    nbits = ((gw + 7) // 8) * 8
    src = [[(row >> (nbits - 1 - x)) & 1 for x in range(gw)] for row in g['rows']]
    return [[src[y * gh // h][x * gw // w] for x in range(w)] for y in range(h)]


def build(bdf=None):
    bdf = bdf or kfont.load_bdf()
    body = [[False] * 128 for _ in range(16)]
    gw, gh, gap = 24, 13, 4
    x = (128 - (len(TEXT) * gw + (len(TEXT) - 1) * gap)) // 2
    for ch in TEXT:
        m = scaled(ch, bdf, gw, gh)
        for y in range(gh):
            for xx in range(gw):
                if m[y][xx]:
                    body[1 + y][x + xx] = True
        x += gw + gap
    P = [[0] * 128 for _ in range(16)]
    for y in range(16):
        for x in range(128):
            if body[y][x]:
                P[y][x] = 1
            elif any(0 <= y + dy < 16 and 0 <= x + dx < 128 and body[y + dy][x + dx]
                     for dy in (-1, 0, 1) for dx in (-1, 0, 1)):
                P[y][x] = 3
    out = bytearray(0x200)
    for row in range(2):
        for t in range(16):
            o = (row * 16 + t) * 16
            for y in range(8):
                for xx in range(8):
                    c = P[row * 8 + y][t * 8 + xx]
                    if c & 1:
                        out[o + 2 * y] |= 0x80 >> xx
                    if c & 2:
                        out[o + 2 * y + 1] |= 0x80 >> xx
    return bytes(out)
