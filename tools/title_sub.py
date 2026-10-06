"""Korean title subtitle drawn into the OBJ tiles of compressed asset 219.

Asset 219 (8 KB) lands at VRAM 0xD800 = OBJ tile 192.  The subtitle row is ten
16x16 sprites at y=104: tiles 192 (tilde) 194 196 198 200 202 204 206 224 192
(tilde again).  Sprite tile 226 is the TM mark of the old logo.  The original
letters use a vertical gradient (colour 15 at the top down to 8) with colour 7
as a down-right shadow, OBJ palette 0.
"""
import kfont

TEXT_TILES = [194, 196, 198, 200, 202, 204, 206, 224]   # 16x16 sprite tiles, left to right
TM_TILE = 226
FIRST_TILE = 192
GRADIENT = [15, 15, 14, 14, 13, 12, 11, 10, 9, 9, 8, 8, 8]
SHADOW = 7


def render_strip(text, bdf, width=128, advance=13, space=7):
    """Colour-indexed 16 x width strip, text centred."""
    glyphs = []
    total = 0
    for ch in text:
        if ch == ' ':
            glyphs.append(None)
            total += space
        else:
            glyphs.append(bdf[ord(ch)])
            total += advance
    total -= advance - 11 if glyphs and glyphs[-1] is not None else 0
    x0 = (width - total) // 2
    body = [[False] * width for _ in range(16)]
    x = x0
    for g in glyphs:
        if g is None:
            x += space
            continue
        w, h, bx, by = g['bbx']
        nbits = ((w + 7) // 8) * 8
        top = 2 + 11 - (by + h)
        for yy, row in enumerate(g['rows']):
            for xx in range(w):
                if (row >> (nbits - 1 - xx)) & 1:
                    body[top + yy][x + bx + xx] = True
        x += advance
    px = [[0] * width for _ in range(16)]
    for y in range(16):
        for x in range(width):
            if body[y][x]:
                px[y][x] = GRADIENT[min(max(y - 2, 0), len(GRADIENT) - 1)]
            elif y and x and body[y - 1][x - 1]:
                px[y][x] = SHADOW
    return px


def tile8(px, ox, oy):
    out = bytearray(32)
    for y in range(8):
        for x in range(8):
            c = px[oy + y][ox + x]
            for p in range(4):
                if (c >> p) & 1:
                    out[(p // 2) * 16 + y * 2 + (p & 1)] |= 0x80 >> x
    return bytes(out)


def patch_asset(asset, text, bdf=None):
    """Return a modified copy of the decompressed asset 219."""
    bdf = bdf or kfont.load_bdf()
    out = bytearray(asset)
    px = render_strip(text, bdf)

    def put(tile, data):
        o = (tile - FIRST_TILE) * 32
        out[o:o + 32] = data
    for i, t in enumerate(TEXT_TILES):
        ox = i * 16
        put(t, tile8(px, ox, 0))
        put(t + 1, tile8(px, ox + 8, 0))
        put(t + 16, tile8(px, ox, 8))
        put(t + 17, tile8(px, ox + 8, 8))
    for t in (TM_TILE, TM_TILE + 1, TM_TILE + 16, TM_TILE + 17):
        put(t, bytes(32))
    return bytes(out)
