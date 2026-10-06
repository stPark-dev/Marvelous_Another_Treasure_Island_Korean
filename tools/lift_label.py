"""上下 lift label in field tileset LZ 11 redrawn as 상하.

The label is two 8x8 tiles (ink colour 10 on colour 1) stored four times in
the asset, once per 128-tile window; those tiles hold nothing else.  Each copy
is replaced by a Galmuri7 syllable in the same two colours.
"""
import scene_text

ASSET = 11
UP_TILES = [53, 181, 437, 565]       # 上
DOWN_TILES = [54, 182, 438, 566]     # 下
BG, INK = 1, 10


def _glyph(ch, bdf):
    g = bdf[ord(ch)]
    w, h, bx, by = g['bbx']
    nbits = ((w + 7) // 8) * 8
    if w + bx > 8 or h > 8:
        raise ValueError('lift label glyph %r too large' % ch)
    px = [[BG] * 8 for _ in range(8)]
    top = 7 - (by + h)
    for yy, row in enumerate(g['rows']):
        for xx in range(w):
            if (row >> (nbits - 1 - xx)) & 1:
                px[top + yy][bx + xx] = INK
    return scene_text._tile_bytes(px)


def build(tiles, bdf=None):
    bdf = bdf or scene_text._font(scene_text.TINY_BDF)
    out = bytearray(tiles)
    for ch, group in (('상', UP_TILES), ('하', DOWN_TILES)):
        t = _glyph(ch, bdf)
        for k in group:
            out[k * 32:k * 32 + 32] = t
    return bytes(out)
