"""Korean glyph rasterizer for the Marvelous 16x16 font format.

A glyph is two renderer codes (left/right 8x16 halves); each code is 32 bytes:
the top 8x8 2bpp tile followed by the bottom 8x8 2bpp tile.  The original font
uses colour 2 for the body and colour 1 for an 8-neighbour outline.
"""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_BDF = os.path.join(os.path.dirname(ROOT), 'galmuri', 'Galmuri11-Bold.bdf')


def load_bdf(path=DEFAULT_BDF):
    glyphs = {}
    cur = None
    with open(path, encoding='utf-8', errors='replace') as f:
        lines = iter(f.read().split('\n'))
    for line in lines:
        if line.startswith('ENCODING'):
            cur = {'enc': int(line.split()[1])}
        elif line.startswith('BBX') and cur is not None:
            w, h, x, y = map(int, line.split()[1:5])
            cur['bbx'] = (w, h, x, y)
        elif line.startswith('DWIDTH') and cur is not None:
            cur['dw'] = int(line.split()[1])
        elif line == 'BITMAP' and cur is not None:
            rows = []
            for row in lines:
                if row == 'ENDCHAR':
                    break
                rows.append(int(row, 16))
            cur['rows'] = rows
            glyphs[cur['enc']] = cur
            cur = None
    return glyphs


def body_mask(g, ascent=11, em_top=2, align='center'):
    """16x16 boolean body mask: glyph centred horizontally, em box at rows em_top..em_top+ascent-1."""
    w, h, bx, by = g['bbx']
    nbits = ((w + 7) // 8) * 8
    m = [[False] * 16 for _ in range(16)]
    ox = (16 - w) // 2 if align == 'center' else 2 + bx
    top = em_top + ascent - (by + h)
    for yy, row in enumerate(g['rows']):
        for xx in range(w):
            if (row >> (nbits - 1 - xx)) & 1:
                X, Y = ox + xx, top + yy
                if not (0 <= X < 16 and 0 <= Y < 16):
                    raise ValueError('glyph U+%04X does not fit the 16x16 cell' % g['enc'])
                m[Y][X] = True
    return m


def colourize(m):
    """Body -> 2, 8-neighbour outline -> 1, background -> 0."""
    px = [[0] * 16 for _ in range(16)]
    for y in range(16):
        for x in range(16):
            if m[y][x]:
                px[y][x] = 2
    for y in range(16):
        for x in range(16):
            if px[y][x]:
                continue
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    yy, xx = y + dy, x + dx
                    if 0 <= yy < 16 and 0 <= xx < 16 and m[yy][xx]:
                        px[y][x] = 1
    return px


def encode(px):
    """16x16 colour indices -> 64 bytes (left code 32 bytes, right code 32 bytes)."""
    out = bytearray()
    for half in range(2):
        for y in range(16):
            p0 = p1 = 0
            for x in range(8):
                c = px[y][half * 8 + x]
                p0 |= (c & 1) << (7 - x)
                p1 |= ((c >> 1) & 1) << (7 - x)
            out += bytes((p0, p1))
    return bytes(out)


def glyph_bytes(ch, bdf, align='center'):
    g = bdf.get(ord(ch))
    if g is None:
        raise KeyError('no glyph for %r' % ch)
    return encode(colourize(body_mask(g, align=align)))
