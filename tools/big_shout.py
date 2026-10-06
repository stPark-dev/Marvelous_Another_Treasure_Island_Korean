"""Korean art for the big-font shout messages (FE 7C).

Pieces are 32x16 (four 8x16 2bpp codes) at EC:E000 + piece*128 (file 0x2CE000),
drawn by 9F:D438.  Message 2947 lays out pieces 0A 0B 03 11 / 0C 0D 0E 12 14-18 /
0F 10 03 13 ("こらー！" + small "いいかげんにしろ！"); 2949-2954 lay out
00 03 06 / 01 04 07 09 / 02 05 08 ("ウッキ～").  Piece 03 is a shared blank, so
column 2 of 2947 rows 0/2 and column 1 of the monkey art row 0 stay empty.
Colours follow the dialogue font: 2 body, 1 outline.
"""
import kfont

BASE = 0x2CE000
PIECES = 0x19

LAYOUT_A = {0: (0, 0), 1: (0, 1), 2: (0, 2), 3: (1, 0), 4: (1, 1), 5: (1, 2),
            6: (2, 0), 7: (2, 1), 8: (2, 2), 9: (3, 1)}
LAYOUT_B = {0x0A: (0, 0), 0x0B: (1, 0), 0x11: (3, 0),
            0x0C: (0, 1), 0x0D: (1, 1), 0x0E: (2, 1), 0x12: (3, 1),
            0x14: (4, 1), 0x15: (5, 1), 0x16: (6, 1), 0x17: (7, 1), 0x18: (8, 1),
            0x0F: (0, 2), 0x10: (1, 2), 0x13: (3, 2)}


def scaled_mask(ch, bdf, w, h):
    g = bdf[ord(ch)]
    gw, gh, bx, by = g['bbx']
    nbits = ((gw + 7) // 8) * 8
    src = [[(row >> (nbits - 1 - x)) & 1 for x in range(gw)] for row in g['rows']]
    return [[src[y * gh // h][x * gw // w] for x in range(w)] for y in range(h)]


def blit(canvas, mask, ox, oy):
    for y, row in enumerate(mask):
        for x, v in enumerate(row):
            if v:
                canvas[oy + y][ox + x] = 2


def outline(canvas):
    H, W = len(canvas), len(canvas[0])
    out = [row[:] for row in canvas]
    for y in range(H):
        for x in range(W):
            if canvas[y][x]:
                continue
            if any(0 <= y + dy < H and 0 <= x + dx < W and canvas[y + dy][x + dx] == 2
                   for dy in (-1, 0, 1) for dx in (-1, 0, 1)):
                out[y][x] = 1
    return out


def art_a(bdf):
    c = [[0] * 128 for _ in range(48)]
    blit(c, scaled_mask('우', bdf, 28, 42), 2, 3)
    blit(c, scaled_mask('끼', bdf, 22, 26), 37, 19)       # small, rows 1-2 only
    blit(c, scaled_mask('끼', bdf, 28, 42), 66, 3)
    blit(c, scaled_mask('~', bdf, 26, 10), 99, 19)          # row 1 only
    return outline(c)


def art_b(bdf):
    c = [[0] * 288 for _ in range(48)]
    blit(c, scaled_mask('이', bdf, 28, 42), 2, 3)
    blit(c, scaled_mask('놈', bdf, 28, 42), 34, 3)
    blit(c, scaled_mask('~', bdf, 26, 10), 67, 19)          # column 2 row 1 only
    blit(c, scaled_mask('!', bdf, 10, 42), 107, 3)
    small = outline([[0] * 160 for _ in range(16)])
    x = 12                                               # centre 136 px in 160
    for ch in '적당히 좀 해라!':
        if ch != ' ':
            px = kfont.colourize(kfont.body_mask(bdf[ord(ch)]))
            for yy in range(16):
                for xx in range(16):
                    if px[yy][xx]:
                        small[yy][xx + x] = px[yy][xx]
        x += 16 if ch != ' ' else 8
    c = outline(c)
    for yy in range(16):
        for xx in range(160):
            if small[yy][xx]:
                c[16 + yy][128 + xx] = small[yy][xx]
    return c


def piece_bytes(canvas, col, row):
    out = bytearray()
    for code in range(4):
        for y in range(16):
            p0 = p1 = 0
            for x in range(8):
                v = canvas[row * 16 + y][col * 32 + code * 8 + x]
                p0 |= (v & 1) << (7 - x)
                p1 |= (v >> 1 & 1) << (7 - x)
            out += bytes((p0, p1))
    return bytes(out)


def build(bdf=None):
    """Return the PIECES*128 bytes that replace file 0x2CE000.."""
    bdf = bdf or kfont.load_bdf()
    a, b = art_a(bdf), art_b(bdf)
    data = bytearray(PIECES * 128)
    for p, (col, row) in LAYOUT_A.items():
        data[p * 128:(p + 1) * 128] = piece_bytes(a, col, row)
    for p, (col, row) in LAYOUT_B.items():
        data[p * 128:(p + 1) * 128] = piece_bytes(b, col, row)
    if any(data[3 * 128:4 * 128]):
        raise ValueError('shared blank piece 03 must stay empty')
    return bytes(data)
