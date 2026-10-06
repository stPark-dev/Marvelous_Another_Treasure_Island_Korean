"""Korean title logo: image -> BG2 tiles (asset 53), map rows 0-15 (asset 56), palette 7.

Title screen facts (docs/survey.md §6.5): BG2 4bpp, logo tiles 512-767 come
from compressed asset 53 (8 KB, VRAM 0x8000), map rows 0-15 from asset 56
(1 KB, VRAM 0xE800), palette 7 colours 1-14 from ROM 0x125B7C; colour 15 is
set to white by code.  Logo map entries use priority + palette 7 (0x3C00).
"""
from PIL import Image

TILE_BASE = 512
MAX_TILES = 256
ENTRY_ATTR = 0x3C00          # priority, palette 7
WHITE = (248, 248, 248)


def snes_color(rgb):
    r, g, b = (c >> 3 for c in rgb[:3])
    return r | g << 5 | b << 10


LOGO_CROP_BOTTOM = 692    # title_ko.png: the 3D letters end here; the subtitle below is drawn as sprites


def prepare(path, width=232, top=16, alpha_cut=128, crop_bottom=LOGO_CROP_BOTTOM):
    """Crop to opaque area, scale to width, place on a 256x128 canvas."""
    im = Image.open(path).convert('RGBA')
    if crop_bottom:
        im = im.crop((0, 0, im.width, crop_bottom))
    mask = im.getchannel('A').point(lambda v: 255 if v > alpha_cut else 0)
    im = im.crop(mask.getbbox())
    h = round(im.height * width / im.width)
    im = im.resize((width, h), Image.LANCZOS)
    canvas = Image.new('RGBA', (256, 128), (0, 0, 0, 0))
    canvas.paste(im, ((256 - width) // 2, top), im)
    if top + h > 128:
        raise ValueError('logo %d px tall does not fit rows 0-15' % h)
    return canvas


def quantize(canvas, ncolors=14, alpha_cut=128):
    """Return (indices 256x128 with 0 = transparent, 1..14 palette, 15 white), palette rgb list[14]."""
    rgb = Image.new('RGB', canvas.size, (0, 0, 0))
    rgb.paste(canvas, (0, 0), canvas)
    alpha = canvas.getchannel('A')
    opaque = [(x, y) for y in range(canvas.height) for x in range(canvas.width) if alpha.getpixel((x, y)) > alpha_cut]
    sample = Image.new('RGB', (len(opaque), 1))
    sample.putdata([rgb.getpixel(p) for p in opaque])
    q = sample.quantize(colors=ncolors, method=Image.MEDIANCUT, dither=Image.NONE)
    pal = q.getpalette()[:ncolors * 3]
    pal = [tuple(pal[i * 3:i * 3 + 3]) for i in range(ncolors)]
    idx = [[0] * canvas.width for _ in range(canvas.height)]
    qd = list(q.getdata())
    for (x, y), c in zip(opaque, qd):
        idx[y][x] = c + 1
    return idx, pal


def tile_bytes(idx, tx, ty):
    out = bytearray(32)
    for y in range(8):
        for x in range(8):
            c = idx[ty * 8 + y][tx * 8 + x]
            for p in range(4):
                if (c >> p) & 1:
                    out[(p // 2) * 16 + y * 2 + (p & 1)] |= 0x80 >> x
    return bytes(out)


def flips(t):
    """Yield (variant bytes, hflip, vflip) for a 4bpp tile."""
    def hf(b):
        return bytes(int('{:08b}'.format(v)[::-1], 2) for v in b)

    def vf(b):
        o = bytearray(32)
        for half in (0, 16):
            for y in range(8):
                o[half + y * 2:half + y * 2 + 2] = b[half + (7 - y) * 2:half + (7 - y) * 2 + 2]
        return bytes(o)
    yield t, 0, 0
    yield hf(t), 1, 0
    yield vf(t), 0, 1
    yield hf(vf(t)), 1, 1


def tile_pixels(t):
    return [sum((((t[(p // 2) * 16 + y * 2 + (p & 1)] >> (7 - x)) & 1) << p) for p in range(4))
            for y in range(8) for x in range(8)]


def reduce_tiles(idx, limit, rgb):
    """Greedy lossy merge: substitute the cheapest tiles until the unique
    (flip-aware) count fits.  Cost = use count x summed squared RGB error."""
    import numpy as np
    cells = {}
    for ty in range(16):
        for tx in range(32):
            t = tile_bytes(idx, tx, ty)
            if t != bytes(32):
                cells[(tx, ty)] = t
    canon = {t: min(v for v, _, _ in flips(t)) for t in set(cells.values())}
    uniq = sorted(set(canon.values()))
    if len(uniq) <= limit:
        return idx
    pal = np.array(rgb, dtype=np.int64)
    base = np.array([pal[tile_pixels(t)] for t in uniq])                       # n x 64 x 3
    var = np.array([[pal[tile_pixels(v)] for v, _, _ in flips(t)] for t in uniq])  # n x 4 x 64 x 3
    n = len(uniq)
    d = np.full((n, n), np.inf)
    for i in range(n):
        diff = ((var - base[i][None, None]) ** 2).sum(axis=(2, 3))   # n x 4
        d[i] = diff.min(axis=1)
        d[i, i] = np.inf
    use = np.zeros(n)
    pos = {t: k for k, t in enumerate(uniq)}
    for t in cells.values():
        use[pos[canon[t]]] += 1
    alive = np.ones(n, bool)
    alias = {}
    while alive.sum() > limit:
        cost = d * use[:, None]
        cost[~alive] = np.inf
        cost[:, ~alive] = np.inf
        a, b = np.unravel_index(np.argmin(cost), cost.shape)
        alias[a] = b
        use[b] += use[a]
        alive[a] = False

    def resolve(k):
        while k in alias:
            k = alias[k]
        return k
    new = [row[:] for row in idx]
    for (tx, ty), t in cells.items():
        k = pos[canon[t]]
        if k in alias:
            r = uniq[resolve(k)]
            orig = pal[tile_pixels(t)]
            best = min(flips(r), key=lambda f: int(((pal[tile_pixels(f[0])] - orig) ** 2).sum()))
            pix = tile_pixels(best[0])
            for m in range(64):
                new[ty * 8 + m // 8][tx * 8 + m % 8] = pix[m]
    return new


def build(path, original_map56, width=232):
    canvas = prepare(path, width=width)
    idx, pal = quantize(canvas)
    rgb = [(0, 0, 0)] + list(pal) + [WHITE]
    idx = reduce_tiles(idx, MAX_TILES - 1, rgb)
    tiles = [bytes(32)]                  # tile 512: blank
    seen = {bytes(32): (0, 0, 0)}
    entries = list(original_map56)
    for ty in range(16):
        for tx in range(32):
            t = tile_bytes(idx, tx, ty)
            orig = original_map56[ty * 32 + tx]
            if t == bytes(32):
                # clear old logo cells, keep everything else
                entries[ty * 32 + tx] = 0 if (orig >> 10) & 7 == 7 else orig
                continue
            hit = None
            for v, h, vflip in flips(t):
                if v in seen:
                    n, h0, v0 = seen[v]
                    hit = (n, h ^ h0, vflip ^ v0)
                    break
            if hit is None:
                n = len(tiles)
                tiles.append(t)
                seen[t] = (n, 0, 0)
                hit = (n, 0, 0)
            n, h, vflip = hit
            entries[ty * 32 + tx] = ENTRY_ATTR | (TILE_BASE + n) | h << 14 | vflip << 15
    if len(tiles) > MAX_TILES:
        raise ValueError('logo needs %d tiles > %d' % (len(tiles), MAX_TILES))
    tiledata = b''.join(tiles) + bytes(32 * (MAX_TILES - len(tiles)))
    mapdata = b''.join(e.to_bytes(2, 'little') for e in entries)
    paldata = b''.join(snes_color(c).to_bytes(2, 'little') for c in pal)
    return tiledata, mapdata, paldata, len(tiles)
