"""Leader-name graphics on the status screen (2bpp, ROM 8D:BA00 = file 0x269A00).

Two 8x8 tile rows of 16 tiles; ディオン / マックス / ジャック occupy 24x16 boxes at
x 0, 24, 48.  Colour 2 body, colour 1 outline (as in the original).
"""
import kfont

BASE = 0x269A00
BOXES = [(0, '디온'), (24, '맥스'), (48, '잭')]


def read(rom):
    P = [[0] * 128 for _ in range(16)]
    for row in range(2):
        for t in range(16):
            o = BASE + (row * 16 + t) * 16
            for y in range(8):
                for x in range(8):
                    P[row * 8 + y][t * 8 + x] = ((rom[o + 2 * y] >> (7 - x)) & 1) | \
                                                (((rom[o + 2 * y + 1] >> (7 - x)) & 1) << 1)
    return P


def write(P):
    out = bytearray(0x200)
    for row in range(2):
        for t in range(16):
            o = (row * 16 + t) * 16
            for y in range(8):
                for x in range(8):
                    c = P[row * 8 + y][t * 8 + x]
                    if c & 1:
                        out[o + 2 * y] |= 0x80 >> x
                    if c & 2:
                        out[o + 2 * y + 1] |= 0x80 >> x
    return bytes(out)


def build(rom, bdf=None):
    bdf = bdf or kfont.load_bdf()
    P = read(rom)
    for x0, name in BOXES:
        body = [[False] * 24 for _ in range(16)]
        gl = [bdf[ord(c)] for c in name]
        width = sum(g['bbx'][0] for g in gl) + (len(gl) - 1)
        x = (24 - width) // 2
        for g in gl:
            w, h, bx, by = g['bbx']
            nbits = ((w + 7) // 8) * 8
            top = 2 + 11 - (by + h)
            for yy, row in enumerate(g['rows']):
                for xx in range(w):
                    if (row >> (nbits - 1 - xx)) & 1:
                        body[top + yy][x + xx] = True
            x += w + 1
        for y in range(16):
            for xx in range(24):
                if body[y][xx]:
                    v = 2
                elif any(0 <= y + dy < 16 and 0 <= xx + dx < 24 and body[y + dy][xx + dx]
                         for dy in (-1, 0, 1) for dx in (-1, 0, 1)):
                    v = 1
                else:
                    v = 0
                P[y][x0 + xx] = v
    return write(P)
