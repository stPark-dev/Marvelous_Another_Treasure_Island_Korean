"""Korean hint-bubble phrases (128x16 2bpp strips at ROM 8D:B000 + i*0x200).

The panel screens stream one strip into VRAM through the 98:89AA transfer
queue.  Background colour 2, letters colour 1 (1 px strokes), icons use
colour 3.  Icons are copied from the original strips; text is Galmuri11.
"""
import os

import kfont

BASE = 0x26B000                      # 8D:B000
STRIP = 0x200
REGULAR_BDF = os.path.join(os.path.dirname(kfont.DEFAULT_BDF), 'Galmuri11.bdf')

# (left icon width copied from the original, text, extra icon (src_x0, src_x1) inserted at '@')
PHRASES = [
    (24, '로 자세히 조사', None),           # Ⓐで、くわしく調べる。
    (24, '로 팀워크다!', None),              # Ⓐで、チームワークだ
    (24, '로 아이템 고르기', None),          # Ⓐで、アイテム選ぼう
    (24, '로 이 화면 끝내기', None),         # Ⓐで、この画面やめる
    (24, '로 @를 움직여', (44, 63)),         # ✚で、☞を動かそう
    (24, '를 눌러 봐!', None),               # Ⓐを押してごらん！
    (0, '여기서는 못 써!', None),            # ここでは、使えないよ！
    (0, '……어라?', None),                   # ・・・・おやっ？
]


def read_strip(rom, i):
    o = BASE + i * STRIP
    P = [[0] * 128 for _ in range(16)]
    for t in range(32):
        tx, ty = (t % 16) * 8, (t // 16) * 8
        for y in range(8):
            for x in range(8):
                P[ty + y][tx + x] = ((rom[o + t * 16 + 2 * y] >> (7 - x)) & 1) | \
                                    (((rom[o + t * 16 + 2 * y + 1] >> (7 - x)) & 1) << 1)
    return P


def write_strip(P):
    out = bytearray(STRIP)
    for t in range(32):
        tx, ty = (t % 16) * 8, (t // 16) * 8
        for y in range(8):
            for x in range(8):
                c = P[ty + y][tx + x]
                if c & 1:
                    out[t * 16 + 2 * y] |= 0x80 >> x
                if c & 2:
                    out[t * 16 + 2 * y + 1] |= 0x80 >> x
    return bytes(out)


def render(orig, icon_w, text, extra, bdf):
    P = [[2] * 128 for _ in range(16)]
    for y in range(16):
        for x in range(icon_w):
            P[y][x] = orig[y][x]
    x = icon_w + (2 if icon_w else 6)
    for ch in text:
        if ch == '@':
            x0, x1 = extra
            for y in range(16):
                for xx in range(x0, x1 + 1):
                    P[y][x + xx - x0] = orig[y][xx]
            x += x1 - x0 + 2
            continue
        g = bdf[ord(ch)]
        w, h, bx, by = g['bbx']
        nbits = ((w + 7) // 8) * 8
        top = 2 + 11 - (by + h)
        for yy, row in enumerate(g['rows']):
            for xx in range(w):
                if (row >> (nbits - 1 - xx)) & 1:
                    if x + bx + xx >= 128:
                        raise ValueError('phrase %r too wide' % text)
                    P[top + yy][x + bx + xx] = 1
        x += g['dw']
    if x > 128:
        raise ValueError('phrase %r too wide (%d px)' % (text, x))
    return P


def build(rom, bdf=None):
    bdf = bdf or kfont.load_bdf(REGULAR_BDF)
    out = bytearray()
    for i, (icon_w, text, extra) in enumerate(PHRASES):
        out += write_strip(render(read_strip(rom, i), icon_w, text, extra, bdf))
    return bytes(out)
