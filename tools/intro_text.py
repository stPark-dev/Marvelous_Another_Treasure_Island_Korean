"""Korean intro story (BG3 picture text).

The intro scrolls a static BG3 picture: 2bpp 16x16 glyph cells (compressed
assets 57/58/59 -> VRAM 0x8000-0xAFFF, tile n with quarters n, n+1, n+16, n+17)
and a 32x64 map (asset 60 -> VRAM 0xE000).  Lines sit every second map row;
the left half holds the story, the right half a copy of the last eight lines
(vertical wrap) and the closing paragraph.  data/intro_ko.json gives the Korean
line for every original line position.
"""
import json
import os

import kfont

CELLS = 192                 # 768 2bpp tiles / 4
BODY = 3


def cell_tile(k):
    return (k // 8) * 32 + (k % 8) * 2


def glyph_cell(ch, bdf):
    """16x16 colour indices for one syllable/punctuation (body colour 3)."""
    px = [[0] * 16 for _ in range(16)]
    if ch == ' ':
        return px
    m = kfont.body_mask(bdf[ord(ch)], align='left' if ch in '.,' else 'center')
    for y in range(16):
        for x in range(16):
            if m[y][x]:
                px[y][x] = BODY
    return px


def cell_bytes(px):
    out = {}
    for q, (ox, oy) in enumerate(((0, 0), (8, 0), (0, 8), (8, 8))):
        t = bytearray(16)
        for y in range(8):
            for x in range(8):
                c = px[oy + y][ox + x]
                if c & 1:
                    t[2 * y] |= 0x80 >> x
                if c & 2:
                    t[2 * y + 1] |= 0x80 >> x
        out[q] = bytes(t)
    return out


def build(orig_map, lines, bdf):
    """Return (sheet 12 KB, map 4 KB, cells used)."""
    ent = [orig_map[2 * i] | orig_map[2 * i + 1] << 8 for i in range(len(orig_map) // 2)]
    counts = {}
    for e in ent:
        counts[e] = counts.get(e, 0) + 1
    blank = max(counts, key=counts.get)
    blank_cell = None
    for k in range(CELLS):
        if cell_tile(k) == blank & 0x3FF:
            blank_cell = k
    placements = []
    for ln in lines:
        placements.append((ln['row'], ln['half'], ln['ko']))
        if 'copy_to' in ln:
            placements.append((ln['copy_to'][1], ln['copy_to'][0], ln['ko']))
    rows = {(r, h) for r, h, _ in placements}
    attr = {}
    for r, h in rows:
        cols = range(h * 16, h * 16 + 16)
        found = [ent[r * 32 + c] for c in cols if ent[r * 32 + c] != blank]
        if not found:
            raise ValueError('row %d half %d has no original text' % (r, h))
        attr[(r, h)] = found[0] & 0xFC00
        for c in cols:
            ent[r * 32 + c] = blank
    sheet = bytearray(CELLS * 64)
    alloc = {' ': None}
    free = [k for k in range(CELLS) if k != blank_cell]
    for r, h, text in placements:
        if len(text) > 15:
            raise ValueError('line %r is %d cells (max 15)' % (text, len(text)))
        start = h * 16 + (16 - len(text)) // 2
        for i, ch in enumerate(text):
            if ch == ' ':
                continue
            if ch not in alloc:
                if not free:
                    raise ValueError('intro needs more than %d glyph cells' % CELLS)
                k = free.pop(0)
                alloc[ch] = k
                q = cell_bytes(glyph_cell(ch, bdf))
                n = cell_tile(k)
                for qi, d in ((0, 0), (1, 1), (2, 16), (3, 17)):
                    sheet[(n + d) * 16:(n + d) * 16 + 16] = q[qi]
            ent[r * 32 + start + i] = attr[(r, h)] | cell_tile(alloc[ch])
    mp = b''.join(e.to_bytes(2, 'little') for e in ent)
    return bytes(sheet), mp, len(alloc) - 1


def load_lines(path=None):
    path = path or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'intro_ko.json')
    with open(path, encoding='utf-8') as f:
        return json.load(f)['lines']
