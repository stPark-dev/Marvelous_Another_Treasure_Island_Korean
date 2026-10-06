"""Korean text redrawn into examine-scene pictures (BG1, D13 "must read").

Examine scenes (tent poster, boards, letters) pick their BG1 map and tiles
from per-scene tables indexed by $358C:
  9F:921F[x]: map asset = 72 + (v >> 1), half = v & 1 (0x1000-byte 64x32 map)
  9F:929B[x]: tile asset = 81 + (v >> 2), the 4 KB at (v & 3) * 0x800 goes to
              BG1 tiles 512-639.
A spec names the scene screen, its visible cells, the cells to rebuild and
the cells to keep (icons); cells outside the visible area may show changed
tiles.  Rebuilt cells start from a background tile, get the Korean text
drawn over them, and are re-tiled: tiles equal to one still used elsewhere
are shared, the rest take tile numbers that nothing outside the rebuilt
cells uses.  Text must stay inside rebuilt cells.
"""
import os

import kfont
import bubble_gfx

SMALL_BDF = os.path.join(os.path.dirname(kfont.DEFAULT_BDF), 'Galmuri9.bdf')
TINY_BDF = os.path.join(os.path.dirname(kfont.DEFAULT_BDF), 'Galmuri7.bdf')
BOLD_BDF = os.path.join(os.path.dirname(kfont.DEFAULT_BDF), 'Galmuri11-Bold.bdf')
LARGE_BDF = os.path.join(os.path.dirname(kfont.DEFAULT_BDF), 'Galmuri14.bdf')
_FONTS = {}


def _font(path):
    if path not in _FONTS:
        _FONTS[path] = kfont.load_bdf(path)
    return _FONTS[path]

LZ_PTR_LO, LZ_PTR_HI, LZ_PTR_BANK = 0x13D5, 0x12DC, 0x11E3
TILE_BASE = 512
WINDOW = 128                      # tiles uploaded per scene


def asset_offset(rom, i):
    p = rom[LZ_PTR_BANK + i] << 16 | rom[LZ_PTR_HI + i] << 8 | rom[LZ_PTR_LO + i]
    return ((p >> 16) - 0xC0) << 16 | (p & 0xFFFF)


def _camp_bg(r, c, orig):
    return TILE_BASE + (0x10 if r & 1 else 0) + (c & 1)


def _parchment_bg(r, c, orig):
    if orig - TILE_BASE < 0x1E:                       # already a parchment tile
        return orig
    return TILE_BASE + 6 * ((r - 17) % 5) + (c - 4) % 6


_CAMP_TEXT = dict(fill=1, shade=3, outline=4)
_TABLET_TEXT = dict(fill=4, outline=None, shadow=14, tracking=0)   # carved: dark with a light lower-right edge
SPECS = {
    # tent poster "??" scene 0x41: キャンプのこころえ！ chalkboard
    'camp_rules': dict(
        map_asset=77, map_half=0, screen=1, tile_asset=95, tile_sub=0,
        visible=(0, 16, 0, 32),                              # rows 16+ sit below the window
        rebuild=[(2, 4, 11, 21), (4, 12, 10, 24)],          # (row0, row1, col0, col1)
        keep=[(r, c) for r in (4, 5, 6, 7) for c in (19, 20)]       # A icons
        + [(r, c) for r in (6, 7) for c in (10, 11)]              # ? icon
        + [(r, c) for r in (8, 9) for c in (19, 20)],             # B icon
        bg=_camp_bg, bg_colours=(5, 6, 8, 9),
        texts=[
            dict(_CAMP_TEXT, x=None, y=16, text='캠프 수칙!', span=(88, 168)),
            dict(_CAMP_TEXT, x=81, y=32, text='어? 싶으면'),
            dict(_CAMP_TEXT, x=97, y=48, text='가 나오면'),
            dict(_CAMP_TEXT, x=81, y=64, text='액션은'),
            dict(_CAMP_TEXT, x=81, y=80, text='곤란할 땐'),
            dict(_CAMP_TEXT, x=137, y=80, text='호루라기!', fill=11, shade=11),
        ] + [dict(_CAMP_TEXT, x=169, y=y, text='버튼', tracking=-1) for y in (32, 48, 64)],
    ),
    # note on the wall, scene 0x47 (right screen, rows 16-31): 1、2つのマドをふく。／2、アナを板でふさぐ。／
    # 3、テーブルを左にくっつける。／以上 (tasks of messages 1251-1253)
    'school_note': dict(
        map_asset=77, map_half=1, screen=1, tile_asset=98, tile_sub=0,
        visible=(16, 32, 0, 32),
        rebuild=[(19, 21, 8, 25), (22, 24, 8, 25), (25, 27, 8, 25), (28, 30, 8, 25)],
        keep=[],
        erase=(6, 7, 14), paper=15, bg_colours=(9, 10, 11, 12, 13, 15),
        texts=[dict(fill=7, outline=None, shadow=14, tracking=0, x=x, y=y, text=t) for x, y, t in (
            (65, 152, '1. 창문 2개를 닦는다.'),
            (65, 176, '2. 구멍을 판자로 막는다.'),
            (65, 200, '3. 테이블을 왼쪽 벽에.'),
            (129, 224, '이상'))],
    ),
    # the colonel's letter, scene 0x66 (left screen, rows 16-31), vertical: 返してあげなさい。／大佐より。
    'colonel_letter': dict(
        map_asset=80, map_half=0, screen=0, tile_asset=105, tile_sub=0,
        visible=(16, 32, 0, 32),
        font=TINY_BDF,
        rebuild=[(21, 29, 11, 15)],
        keep=[],
        erase=(4, 9, 12, 13, 14), paper=15, bg_colours=(15,),
        texts=[dict(fill=9, outline=None, vertical=True, x=x, y=y, text=t) for x, y, t in (
            (104, 176, '돌려주거라.'),
            (88, 176, '대령으로부터'))],
    ),
    # taunting note, scene 0x2F (right screen, rows 0-15): ざんねんでした！／力のつづくかぎり／
    # ず～とさがしてろ！／バーカ (quoted in message 0793)
    'taunt_note': dict(
        map_asset=75, map_half=1, screen=1, tile_asset=90, tile_sub=0,
        visible=(0, 16, 0, 32),
        clear=[(52, 14, 204, 52), (52, 52, 112, 61), (112, 52, 180, 56),   # big words, above the face
               (38, 64, 119, 80), (48, 80, 119, 97), (94, 99, 127, 113)],
        keep=[], paper=14, bg_colours=(14,),
        texts=[dict(fill=6, outline=3, tracking=0, scale=1, x=64, y=16, text='아쉽게', font=BOLD_BDF),
               dict(fill=6, outline=3, tracking=0, scale=1, x=120, y=32, text='됐군!', font=BOLD_BDF),
               dict(fill=3, outline=None, tracking=0, x=39, y=64, text='힘이 닿는 데까지', font=SMALL_BDF),
               dict(fill=6, outline=None, tracking=0, x=50, y=81, text='계~속', font=SMALL_BDF),
               dict(fill=3, outline=None, tracking=0, x=82, y=81, text='찾아라!', font=SMALL_BDF),
               dict(fill=3, outline=None, tracking=0, x=96, y=98, text='바~보', font=SMALL_BDF)],
    ),
    # hand-drawn map, scenes 0x31/0x5F (right screen, rows 0-15): たすけて！／ココ／テント
    'rescue_map': dict(
        map_asset=72, map_half=1, screen=1, tile_asset=83, tile_sub=0,
        visible=(0, 16, 0, 32),
        clear=[(40, 40, 75, 51), (68, 28, 85, 36), (136, 80, 152, 90)],
        keep=[], paper=10, bg_colours=(10,),
        texts=[dict(fill=1, outline=None, tracking=0, x=40, y=38, text='살려줘!', font=SMALL_BDF),
               dict(fill=1, outline=None, tracking=0, x=69, y=22, text='여기', font=TINY_BDF),
               dict(fill=5, outline=None, tracking=0, x=137, y=74, text='텐트', font=TINY_BDF)],
    ),
    # wooden sign, scene 0x21 (right screen, rows 0-15): 立ち入り禁止！／ご用の方は、管理事務所まで
    'keep_out_sign': dict(
        map_asset=74, map_half=0, screen=1, tile_asset=86, tile_sub=2,
        visible=(0, 16, 0, 32),
        protect_tiles=list(range(128 + 0x50, 128 + 0x78)),   # scene 0x2B (map 75/0 bottom-left) shares window 86/2
        rebuild=[(4, 6, 7, 21), (8, 10, 7, 23)],
        keep=[],
        erase=(14, 15), paper=11, bg_colours=(2, 3, 4, 5, 6, 9, 11),
        texts=[dict(fill=15, outline=None, shadow=2, tracking=0, x=75, y=34, text='출입 금지!', font=LARGE_BDF),
               dict(fill=15, outline=None, shadow=2, tracking=0, x=57, y=63, text='볼일은 관리사무소로',
                    font=SMALL_BDF)],
    ),
    # Benson's grave note, scene 0x40 (left screen, rows 16-31): 少年たちへ／黒い石を
    # ミナミ、キタ、ニシ、ヒガシの順にふんでみろ／そこにはキボウがうまっている／ベンソン
    'benson_tablet': dict(
        map_asset=77, map_half=0, screen=0, tile_asset=94, tile_sub=2,
        visible=(16, 32, 0, 32),
        font=SMALL_BDF,
        rebuild=[(20, 30, 6, 23)],
        keep=[],
        bg=_parchment_bg, bg_colours=(10, 11, 12, 13),
        texts=[dict(_TABLET_TEXT, x=x, y=y, text=s) for x, y, s in (
            (72, 156, '소년들에게'),
            (52, 170, '검은 돌을 남북서동'),
            (52, 184, '순서로 밟아라'),
            (52, 198, '그곳에 희망이 묻혀 있다'),
            (140, 212, '벤슨'))],
    ),
}

BASELINE = 13                     # glyph baseline inside a 16 px text row
TRACKING = 1
SPACE_W = 4


def rebuild_cells(spec):
    keep = set(spec['keep'])
    if 'clear' in spec:
        return {(y // 8, x // 8) for x0, y0, x1, y1 in spec['clear'] for y in range(y0, y1) for x in range(x0, x1)} - keep
    return {(r, c) for r0, r1, c0, c1 in spec['rebuild'] for r in range(r0, r1) for c in range(c0, c1)
            if (r, c) not in keep}


def owned_pixels(spec):
    """Pixels the build may repaint: the clear boxes, or every pixel of the rebuilt cells."""
    if 'clear' in spec:
        return {(x, y) for x0, y0, x1, y1 in spec['clear'] for y in range(y0, y1) for x in range(x0, x1)}
    return {(c * 8 + x, r * 8 + y) for r, c in rebuild_cells(spec) for y in range(8) for x in range(8)}


def _tile_pixels(tiles, k):
    o = k * 32
    return [[sum(((tiles[o + (p // 2) * 16 + 2 * y + (p & 1)] >> (7 - x)) & 1) << p for p in range(4))
             for x in range(8)] for y in range(8)]


def _tile_bytes(px):
    out = bytearray(32)
    for y in range(8):
        for x in range(8):
            for p in range(4):
                if (px[y][x] >> p) & 1:
                    out[(p // 2) * 16 + 2 * y + (p & 1)] |= 0x80 >> x
    return bytes(out)


def render_screen(tiles, ent, spec):
    lo = spec['tile_sub'] * 64
    pix = [[0] * 256 for _ in range(256)]
    for i, e in enumerate(ent):
        r, c = divmod(i, 32)
        px = _tile_pixels(tiles, (e & 0x3FF) - TILE_BASE + lo)
        for y in range(8):
            for x in range(8):
                pix[r * 8 + y][c * 8 + x] = px[7 - y if e >> 15 & 1 else y][7 - x if e >> 14 & 1 else x]
    return pix


def _advance(ch, bdf, tracking=TRACKING):
    if ch == ' ':
        return SPACE_W
    return bdf[ord(ch)]['dw'] + (tracking if '가' <= ch <= '힣' else 0)


def _draw(pix, owner, item, bdf):
    """Draw one text item; owner[y][x] marks pixels that may change."""
    if item.get('font'):
        bdf = _font(item['font'])
    tr = item.get('tracking', TRACKING)
    width = sum(_advance(ch, bdf, tr) for ch in item['text'])
    x = item['x'] if item['x'] is not None else (item['span'][0] + item['span'][1] - width) // 2
    y = item['y']
    glyph = {}
    for ch in item['text']:
        g = bdf[ord(ch)]
        w, h, bx, by = g['bbx']
        nbits = ((w + 7) // 8) * 8
        k = item.get('scale', 1)
        if item.get('vertical'):          # one syllable per line, glyph tops on a fixed pitch
            top = y + item.get('ascent', 7) - (by + h)
        else:
            top = item['y'] + k * (BASELINE - 2) + 2 - k * (by + h)
        for yy, row in enumerate(g['rows']):
            for xx in range(w):
                if (row >> (nbits - 1 - xx)) & 1:
                    for sy in range(k):
                        for sx in range(k):
                            gy = top + yy * k + sy
                            glyph[(x + (bx + xx) * k + sx, gy)] = (gy - (item['y'] + 2)) // k
        if item.get('vertical'):
            y += item.get('pitch', 9)
        else:
            x += _advance(ch, bdf, tr) * k
    if item.get('outline') is not None:
        edge, colour = {(gx + dx, gy + dy) for gx, gy in glyph for dx in (-1, 0, 1) for dy in (-1, 0, 1)}, item['outline']
    elif item.get('shadow') is not None:
        edge, colour = {(gx + 1, gy + 1) for gx, gy in glyph}, item['shadow']
    else:
        edge, colour = set(), None
    edge -= set(glyph)
    for (px, py) in list(glyph) + list(edge):
        if not (0 <= px < 256 and 0 <= py < 256) or not owner[py][px]:
            raise ValueError('text %r leaves the rebuilt cells at (%d, %d)' % (item['text'], px, py))
    for px, py in edge:
        pix[py][px] = colour
    for (px, py), dy in glyph.items():
        pix[py][px] = item['fill'] if dy < 6 else item.get('shade', item['fill'])


def _erased(cell, erase, paper):
    """Replace text colours with the nearest other pixel in the same column (then row) of the cell."""
    out = [row[:] for row in cell]
    for y in range(8):
        for x in range(8):
            if cell[y][x] not in erase:
                continue
            near = [cell[yy][x] for d in range(1, 8) for yy in (y - d, y + d)
                    if 0 <= yy < 8 and cell[yy][x] not in erase]
            near = near or [cell[y][xx] for d in range(1, 8) for xx in (x - d, x + d)
                            if 0 <= xx < 8 and cell[y][xx] not in erase]
            out[y][x] = near[0] if near else paper
    return out


def build(tiles, mp, spec, bdf=None):
    bdf = bdf or _font(spec.get('font', bubble_gfx.REGULAR_BDF))
    base = spec['map_half'] * 0x800 + spec['screen'] * 0x400
    ent = [mp[2 * (base + i)] | mp[2 * (base + i) + 1] << 8 for i in range(1024)]
    lo = spec['tile_sub'] * 64
    cells = rebuild_cells(spec)
    v0, v1, h0, h1 = spec.get('visible', (0, 32, 0, 32))
    used = {(e & 0x3FF) - TILE_BASE for i, e in enumerate(ent)
            if divmod(i, 32) not in cells and v0 <= i // 32 < v1 and h0 <= i % 32 < h1}
    if any(not 0 <= k < WINDOW for k in used):
        raise ValueError('scene references tiles outside its window')
    protect = {k - lo for k in spec.get('protect_tiles', ())}
    free = [k for k in range(WINDOW) if k not in used and k not in protect]

    pix = render_screen(tiles, ent, spec)
    owner = [[False] * 256 for _ in range(256)]
    if 'clear' in spec:
        for x, y in owned_pixels(spec):
            pix[y][x] = spec['paper']
            owner[y][x] = True
    for r, c in cells:
        if 'clear' in spec:
            continue
        if 'erase' in spec:
            bg = _erased([row[c * 8:c * 8 + 8] for row in pix[r * 8:r * 8 + 8]], spec['erase'], spec['paper'])
        else:
            bg = _tile_pixels(tiles, spec['bg'](r, c, ent[r * 32 + c] & 0x3FF) - TILE_BASE + lo)
        for y in range(8):
            for x in range(8):
                pix[r * 8 + y][c * 8 + x] = bg[y][x]
                owner[r * 8 + y][c * 8 + x] = True
    for item in spec['texts']:
        _draw(pix, owner, item, bdf)

    nt = bytearray(tiles)
    nm = bytearray(mp)
    known = {bytes(tiles[(lo + k) * 32:(lo + k + 1) * 32]): k for k in sorted(used)}
    for r, c in sorted(cells):
        t = _tile_bytes([row[c * 8:c * 8 + 8] for row in pix[r * 8:r * 8 + 8]])
        if t not in known:
            if not free:
                raise ValueError('scene %s needs more than %d tiles' % (spec.get('name', '?'), WINDOW - len(protect)))
            k = free.pop(0)
            nt[(lo + k) * 32:(lo + k + 1) * 32] = t
            known[t] = k
        i = base + r * 32 + c
        e = (ent[r * 32 + c] & 0x1C00) | 0x2000 & ent[r * 32 + c] | (TILE_BASE + known[t])
        nm[2 * i:2 * i + 2] = e.to_bytes(2, 'little')
    return bytes(nt), bytes(nm)


def apply_all(rom):
    """Apply every spec in order; returns {asset index: new raw bytes}."""
    import lz2
    out = {}
    for name, spec in SPECS.items():
        spec = dict(spec, name=name)
        for a in (spec['tile_asset'], spec['map_asset']):
            if a not in out:
                out[a] = lz2.decompress(rom, asset_offset(rom, a))
        out[spec['tile_asset']], out[spec['map_asset']] = build(out[spec['tile_asset']], out[spec['map_asset']], spec)
    return out
