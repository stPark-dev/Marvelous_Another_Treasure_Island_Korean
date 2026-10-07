"""Dialogue insert icons [FE6D48] (チーム/ワーク) and [FE6D4A] (アイテム) as 팀워크 / 아이템.

The icons are 32x16 2bpp pictures in the sheet at 8D:E000 (file 0x26E000,
16 tiles per row, so the second tile row is +0x100).  The dialogue window is
hi-res, so each icon shows as two text cells.  Frame: row 0 and column 0/31
colour 1, row 1 colour 2, row 15 colour 1; the interior (rows 2-14, columns
1-30) is colour 3 with the label in colour 2 and a colour 1 shadow.
"""
import scene_text

ROW = 0x100
ICONS = {0x26E6C0: '팀워크', 0x26E880: '아이템'}
EDGE, TEXT, BG = 1, 2, 3
TOP = 4                                  # glyph top row (Galmuri9, 9 px)


def read_icon(rom, base):
    px = [[0] * 32 for _ in range(16)]
    for ty in range(2):
        for tx in range(4):
            o = base + ty * ROW + tx * 16
            for y in range(8):
                lo, hi = rom[o + 2 * y], rom[o + 2 * y + 1]
                for x in range(8):
                    px[ty * 8 + y][tx * 8 + x] = ((lo >> (7 - x)) & 1) | (((hi >> (7 - x)) & 1) << 1)
    return px


def _label(px, text, bdf):
    on = set()
    width = sum(bdf[ord(ch)]['dw'] for ch in text[:-1]) + bdf[ord(text[-1])]['bbx'][0]
    x = 1 + (30 - width) // 2
    if x < 1:
        raise ValueError('icon label %r too wide' % text)
    for ch in text:
        g = bdf[ord(ch)]
        w, h, bx, by = g['bbx']
        nbits = ((w + 7) // 8) * 8
        top = TOP + 9 - (by + h)
        for yy, row in enumerate(g['rows']):
            for xx in range(w):
                if (row >> (nbits - 1 - xx)) & 1:
                    on.add((x + bx + xx, top + yy))
        x += g['dw']
    for y in range(2, 15):
        for xx in range(1, 31):
            px[y][xx] = BG
    for gx, gy in on:                     # lower-right shadow; a full outline would fill the 1 px gaps
        if 1 <= gx + 1 <= 30 and 2 <= gy + 1 <= 14:
            px[gy + 1][gx + 1] = EDGE
    for gx, gy in on:
        if not (1 <= gx <= 30 and 2 <= gy <= 14):
            raise ValueError('icon label %r leaves the frame' % text)
        px[gy][gx] = TEXT


def build(rom, bdf=None):
    """Return {file offset: 16-byte tile} for both icons."""
    bdf = bdf or scene_text._font(scene_text.SMALL_BDF)
    out = {}
    for base, text in ICONS.items():
        px = read_icon(rom, base)
        _label(px, text, bdf)
        for ty in range(2):
            for tx in range(4):
                t = bytearray(16)
                for y in range(8):
                    for x in range(8):
                        v = px[ty * 8 + y][tx * 8 + x]
                        t[2 * y] |= (v & 1) << (7 - x)
                        t[2 * y + 1] |= (v >> 1) << (7 - x)
                out[base + ty * ROW + tx * 16] = bytes(t)
    return out
