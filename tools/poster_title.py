"""Camp poster title (キャンプのまえにおぼえよう！) redrawn in Korean.

The poster is BG1 (palette 7): tiles from LZ asset 99 (bytes 0-0xFFF go to BG1 tiles 512-639),
map from LZ asset 78: bytes 0x1000-0x1FFF go to the 64x32 BG1 map; rows 0-15
of its left screen (entries 0x800-0xBFF) show through the window.  The title
fills map rows 3-4, cols 6-19 and its 28 tiles are shown nowhere else, so
they are redrawn in place.  The map stays untouched: scenes 4F-55 show the
same map half with tile asset 100.

Style follows the original: cream fill (colour 12) with a 1 px outline,
dark red (1) for the camp word and dark green (14) for the rest, on white (15).
"""
import kfont
import bubble_gfx

TILES_OFFSET = 0x14A478          # asset 99 (D4:A478)
MAP_OFFSET = 0x12E9BA            # asset 78 (D2:E9BA)
TILES_ASSET, MAP_ASSET = 99, 78
MAP_BASE = 0x800
VISIBLE_ROWS = range(16)         # rows 16+ sit below the window
ROWS = (3, 4)
COL0, COL1 = 6, 20               # title cells [COL0, COL1)
BG, FILL, RED, GREEN = 15, 12, 1, 14
BASELINE = 14
TRACKING = 1                     # extra px after each syllable so outlines stay apart
SPACE_W = 3
TEXT = [('캠프', RED), (' 전에 익히자!', GREEN)]


def title_tiles(ent):
    """Tile numbers of the redrawable title cells; each must be shown only there."""
    own = [ent[MAP_BASE + r * 32 + c] & 0x3FF for r in ROWS for c in range(COL0, COL1)]
    for n in own:
        if sum(1 for r in VISIBLE_ROWS for c in range(32) if ent[MAP_BASE + r * 32 + c] & 0x3FF == n) != 1:
            raise ValueError('poster title tile %03X is shared' % n)
    return set(own)


def _get(tiles, n, x, y):
    o = (n - 512) * 32
    return sum(((tiles[o + (p // 2) * 16 + 2 * y + (p & 1)] >> (7 - x)) & 1) << p for p in range(4))


def read_rect(tiles, ent):
    w = (COL1 - COL0) * 8
    pix = [[0] * w for _ in range(16)]
    for ri, r in enumerate(ROWS):
        for c in range(COL0, COL1):
            n = ent[MAP_BASE + r * 32 + c] & 0x3FF
            for y in range(8):
                for x in range(8):
                    pix[ri * 8 + y][(c - COL0) * 8 + x] = _get(tiles, n, x, y)
    return pix


def _advance(ch, bdf):
    if ch == ' ':
        return SPACE_W
    return bdf[ord(ch)]['dw'] + (TRACKING if '가' <= ch <= '힣' else 0)


def render(text, bdf):
    w = (COL1 - COL0) * 8
    fill = [[0] * w for _ in range(16)]          # 0 = none, else outline colour
    width = sum(_advance(ch, bdf) for s, _ in text for ch in s)
    x = (w - width) // 2
    if x < 1:
        raise ValueError('poster title too wide (%d px)' % width)
    for s, colour in text:
        for ch in s:
            g = bdf[ord(ch)]
            gw, gh, bx, by = g['bbx']
            nbits = ((gw + 7) // 8) * 8
            top = BASELINE - (by + gh)
            if top < 0 or x + bx < 0 or top + gh > 16 or x + bx + gw > w:
                raise ValueError('poster glyph %r outside the title cells' % ch)
            for yy, row in enumerate(g['rows']):
                for xx in range(gw):
                    if (row >> (nbits - 1 - xx)) & 1:
                        fill[top + yy][x + bx + xx] = colour
            x += _advance(ch, bdf)
    pix = [[BG] * w for _ in range(16)]
    for y in range(16):
        for x in range(w):
            if fill[y][x]:
                pix[y][x] = FILL
                continue
            near = [fill[y + dy][x + dx] for dy in (-1, 0, 1) for dx in (-1, 0, 1)
                    if 0 <= y + dy < 16 and 0 <= x + dx < w and fill[y + dy][x + dx]]
            if near:
                pix[y][x] = near[0]
    return pix


def build(tiles, mp, text=TEXT, bdf=None):
    """Return the new tile asset; the map is only read."""
    bdf = bdf or kfont.load_bdf(bubble_gfx.REGULAR_BDF)
    ent = [mp[2 * i] | mp[2 * i + 1] << 8 for i in range(len(mp) // 2)]
    title_tiles(ent)
    if any(ent[MAP_BASE + r * 32 + c] >> 14 for r in ROWS for c in range(COL0, COL1)):
        raise ValueError('flipped poster title cell')
    pix = render(text, bdf)
    nt = bytearray(tiles)
    for ri, r in enumerate(ROWS):
        for c in range(COL0, COL1):
            o = ((ent[MAP_BASE + r * 32 + c] & 0x3FF) - 512) * 32
            nt[o:o + 32] = bytes(32)
            for y in range(8):
                for x in range(8):
                    v = pix[ri * 8 + y][(c - COL0) * 8 + x]
                    for p in range(4):
                        if (v >> p) & 1:
                            nt[o + (p // 2) * 16 + 2 * y + (p & 1)] |= 0x80 >> x
    return bytes(nt)
