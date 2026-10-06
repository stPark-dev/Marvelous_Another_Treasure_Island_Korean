"""Product build: Korean Marvelous ROM from the immutable Japanese source.

  python tools/build.py [--policy dev|release] [--out build/marvelous_ko_v<VERSION>.sfc]

Inputs: rom/baserom.sfc (verified by SHA-256), text/ko/*.json translations,
Galmuri bitmap font.  Every changed byte is declared in a WritePlan.
"""
import argparse
import glob
import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import kfont      # noqa: E402
import lz2        # noqa: E402
import title_logo  # noqa: E402
import title_sub   # noqa: E402
import intro_text  # noqa: E402
import big_shout   # noqa: E402
import panel_gfx   # noqa: E402
import bubble_gfx  # noqa: E402
import small_names  # noqa: E402
import ui_pool    # noqa: E402
import hud_logo   # noqa: E402
import poster_title  # noqa: E402
import scene_text  # noqa: E402
import riddle_text  # noqa: E402
import credits_text  # noqa: E402
import lift_label  # noqa: E402
import koenc      # noqa: E402
import mvscript   # noqa: E402
from dis65816 import lorom_to_file   # noqa: E402
from writeplan import WritePlan, verify, PlanError   # noqa: E402

ROOT = mvscript.ROOT
VERSION = '0.1.0'                 # also stated in README.md (test_readme_states_build_version)
SOURCE_SHA256 = '555d78c9e4667bee7fb503efd87ed9fc82c55b0e8bde034a10aa2a53967762c5'
OUT_SIZE = 0x400000

NEW_SCRIPT = 0x300000          # F0:0000
NEW_SCRIPT_BANK = 0xF0
NEW_KANJI = 0x340000           # F4:0000, pages FD/FC/F4 at +0/+0x4000/+0x8000
NEW_KANJI_BANK = 0xF4
KANA_FONT = 0x2AC000           # EA:C000, one-byte codes, 64 bytes per glyph
PAGE_ORDER = ['FD', 'FC', 'F4', 'F7']   # F7: added fourth page, codes 0800-09FF

# One-byte codes 00-9F are also the name-entry grid values (98:8F22 page base
# 00/50 + 98:8F25 cell offset), so they hold a fixed set of name syllables
# (data/name_entry.json).  E9-EF (倶楽部隊団会族 on the alphanumeric page) also
# become team-name syllables.  Every other script syllable goes to a page.
ONE_BYTE_SLOTS = []
FIXED = {}
for i, d in enumerate('0123456789'):
    FIXED[d] = FIXED[chr(0xFF10 + i)] = bytes([0xD4 + i])
for i in range(26):
    FIXED[chr(0x41 + i)] = FIXED[chr(0xFF21 + i)] = bytes([0xA0 + i])
    FIXED[chr(0x61 + i)] = FIXED[chr(0xFF41 + i)] = bytes([0xBA + i])
FIXED.update({'?': b'\xde', '？': b'\xde', '!': b'\xdf', '！': b'\xdf', 'ー': b'\xe0',
              '·': b'\xe1', '・': b'\xe1', ',': b'\xe2', '.': b'\xe3', '~': b'\xe5', '～': b'\xe5',
              '「': b'\xe6', '」': b'\xe7', '/': b'\xe8', '／': b'\xe8'})


def load_name_entry(path=None):
    path = path or os.path.join(ROOT, 'data', 'name_entry.json')
    with open(path, encoding='utf-8') as f:
        ne = json.load(f)
    fixed = {}
    for base, chars in ((0x00, ne['page0']), (0x50, ne['page1']), (0xE9, ne['e9_ef'])):
        for i, ch in enumerate(chars):
            if ch in fixed or ch in FIXED:
                raise ValueError('name syllable %r listed twice' % ch)
            fixed[ch] = bytes([base + i])
    if len(ne['page0']) != 80 or len(ne['page1']) != 80 or len(ne['e9_ef']) != 7:
        raise ValueError('name pages must hold 80/80/7 syllables')
    return fixed


NAME_FIXED = load_name_entry()

# A glyph that renderers draw (unlike F0, which they skip): used where a pool
# slot must overwrite whatever an earlier screen left in the shared sheet buffer.
DRAWN_BLANK = '\u3164'

# 9F:D7AE/D7D7 draw the counter glyph 個 (code 0526/0527 = page FC slot 93)
# after numbers; that slot keeps a fixed Korean counter.
RESERVED_GLYPHS = {b'\xfc\x93': '개'}

# Korean-style punctuation redrawn over the Japanese 、。 glyphs
REDRAW = {0xE2: ',', 0xE3: '.'}

# Movable layout tokens: line break and page wait.  Every other control keeps
# its sequence (see docs/survey.md §2).
MOVABLE = {b'\xf8', b'\xf9'}
MAX_LINE_HALF_CELLS = 44       # 22 cells x 16 px per canvas row

# Code patches: (owner, cpu address, expected bytes, new bytes)
HALF_SPACE_HANDLER = 0x9FFF9C
HALF_SPACE_CODE = bytes([
    0xC2, 0x20,             # REP #$20
    0xE6, 0x9A,             # INC $9A   consume the control byte
    0xE6, 0x9C,             # INC $9C   advance one 8 px column
    0xA5, 0x9C,             # LDA $9C
    0x89, 0x10, 0x00,       # BIT #$0010
    0xF0, 0x06,             # BEQ +6
    0x18,                   # CLC
    0x69, 0x10, 0x00,       # ADC #$0010 skip the bottom-tile half of the row
    0x85, 0x9C,             # STA $9C
    0xE2, 0x20,             # SEP #$20
    0x60,                   # RTS
])
# The glyph renderers advance $9C between the two halves of a glyph without the
# bottom-tile skip.  Original text always starts glyphs on even columns; a half
# space can start one at column x0F, so the shared blit 9F:BF97 normalizes X.
BLIT_FIX = HALF_SPACE_HANDLER + len(HALF_SPACE_CODE)
BLIT_FIX_CODE = bytes([
    0x8A,                   # TXA
    0x89, 0x00, 0x01,       # BIT #$0100   column bit 4 (X = column * 16)
    0xF0, 0x05,             # BEQ +5
    0x18,                   # CLC
    0x69, 0x00, 0x01,       # ADC #$0100
    0xAA,                   # TAX
    0xA0, 0x00, 0x00,       # LDY #$0000   displaced original instruction
    0x60,                   # RTS
])
# Fourth page: decoder handler for F7 (copy of the F4 handler 9F:BB02 with hi byte 08)
F7_HANDLER = BLIT_FIX + len(BLIT_FIX_CODE)
F7_HANDLER_CODE = bytes.fromhex('e220c8b7040aa69a9f01a4401a9f03a440b7040a'
                                'a90869009f00a4409f02a440c220c8e8e8e8e84c53ba')
# AND #$07FF before SBC #$0200 in every kanji glyph fetch -> 12-bit codes
KANJI_MASK_SITES = [0x00F319, 0x00F357, 0x989FF9, 0x98A030, 0x9FBD7B, 0x9FBDAF, 0x9FDFB7, 0x9FDFEB]
CODE_PATCHES = [
    ('script base lo', 0x00FC82, b'\xa9\x00\xb4', b'\xa9\x00\x00'),
    ('script base bank', 0x00FC8B, b'\xa9\xe1\x00', bytes([0xA9, NEW_SCRIPT_BANK, 0x00])),
    ('builder len F4=2', 0x00FC52, b'\x01', b'\x02'),
    ('kanji bank SA-1 copy', 0x00F32F, b'\xa9\xe7\x00', bytes([0xA9, NEW_KANJI_BANK, 0x00])),
    ('kanji bank menu', 0x98A00F, b'\xa9\xe7\x00', bytes([0xA9, NEW_KANJI_BANK, 0x00])),
    ('kanji bank dialogue', 0x9FBD91, b'\xa9\xe7\x00', bytes([0xA9, NEW_KANJI_BANK, 0x00])),
    ('kanji bank D7', 0x9FD7C4, b'\xa9\xe7\x00', bytes([0xA9, NEW_KANJI_BANK, 0x00])),
    ('kanji bank DF', 0x9FDFCD, b'\xa9\xe7\x00', bytes([0xA9, NEW_KANJI_BANK, 0x00])),
    ('decoder F3 -> ctrl 65', 0x9FBA0E, b'\x64', b'\x65'),
    ('render ctrl 65 -> half space', 0x9FBC6B, b'\x76\xc1', (HALF_SPACE_HANDLER & 0xFFFF).to_bytes(2, 'little')),
    ('half space handler', HALF_SPACE_HANDLER, b'\xff' * len(HALF_SPACE_CODE), HALF_SPACE_CODE),
    ('blit column fix call', 0x9FBF97, b'\xa0\x00\x00', b'\x20' + (BLIT_FIX & 0xFFFF).to_bytes(2, 'little')),
    ('blit column fix helper', BLIT_FIX, b'\xff' * len(BLIT_FIX_CODE), BLIT_FIX_CODE),
    # second renderer (dispatch 9F:DEB6, blit 9F:E02E, e.g. the 9F:DD.. caption windows)
    ('render2 ctrl 65 -> half space', 0x9FDEBC, b'\x76\xc1', (HALF_SPACE_HANDLER & 0xFFFF).to_bytes(2, 'little')),
    ('blit2 column fix call', 0x9FE02E, b'\xa0\x00\x00', b'\x20' + (BLIT_FIX & 0xFFFF).to_bytes(2, 'little')),
    ('builder len F7=2', 0x00FC55, b'\x01', b'\x02'),
    ('decoder F7 -> page 3', 0x9FBA2A, b'\x2c\xbb', (F7_HANDLER & 0xFFFF).to_bytes(2, 'little')),
    ('F7 page handler', F7_HANDLER, b'\xff' * len(F7_HANDLER_CODE), F7_HANDLER_CODE),
] + [('kanji mask %06X' % a, a, b'\x29\xff\x07', b'\x29\xff\x0f') for a in KANJI_MASK_SITES]


# Compressed-asset pointer table used by the SA-1 decompressor 00:B904
LZ_PTR_LO, LZ_PTR_HI, LZ_PTR_BANK = 0x13D5, 0x12DC, 0x11E3
LOGO_TILES_ASSET, LOGO_MAP_ASSET, TITLE_OBJ_ASSET = 53, 56, 219
TITLE_SUBTITLE = '또 하나의 보물섬'
INTRO_SHEET_ASSETS, INTRO_MAP_ASSET = (57, 58, 59), 60
LOGO_PALETTE = 0x125B7C            # palette 7 colours 1-14
ASSET_AREA = 0x350000              # after the four kanji pages
LOGO_IMAGE = os.path.join(ROOT, 'title_ko.png')


class BuildError(Exception):
    pass


def load_layout_policy(path=None):
    path = path or os.path.join(ROOT, 'data', 'layout_policy.json')
    with open(path, encoding='utf-8') as f:
        d = json.load(f)
    pol = {}
    for kind in ('pool', 'item'):
        for a, b in d[kind]:
            for i in range(a, b + 1):
                pol[i] = kind
    return pol


LAYOUT = load_layout_policy()
MAX_ITEM_HALF_CELLS = 28


def layout_problems(mid, src_raw, ko):
    """Display-geometry violations of a translated message, by its layout policy."""
    kind = LAYOUT.get(mid, 'dialogue')
    if kind == 'pool':
        toks, _ = mvscript.tokenize(bytes.fromhex(src_raw), 0)
        want = len([1 for k, _ in toks if k in ('kana', 'kanji')])
        ktoks = koenc.parse(ko)
        got = len([1 for k, _ in ktoks if k in ('char', 'full')])
        out = []
        if got != want:
            out.append('pool glyph count %d != source %d' % (got, want))
        if any(k == 'half' for k, _ in ktoks):
            out.append('pool must not use half-width spaces')
        return out
    if kind == 'item':
        ko = ko.replace(' ', '\u3000')
    limit = MAX_ITEM_HALF_CELLS if kind == 'item' else MAX_LINE_HALF_CELLS
    return ['line %d is %.1f cells (max %d)' % (i + 1, w / 2, limit // 2)
            for i, w in enumerate(koenc.line_widths(ko)) if w > limit]


def load_translations(path=None):
    path = path or os.path.join(ROOT, 'text', 'ko')
    entries = {}
    for fn in sorted(glob.glob(os.path.join(path, '*.json'))):
        with open(fn, encoding='utf-8') as f:
            doc = json.load(f)
        for e in doc['entries']:
            if e['id'] in entries:
                raise BuildError('message %d translated in two files (%s)' % (e['id'], fn))
            e['_file'] = os.path.basename(fn)
            entries[e['id']] = e
    return entries


def protected_sequence(raw_or_text):
    """Control tokens other than line/page breaks, in order."""
    if isinstance(raw_or_text, (bytes, bytearray)):
        toks, _ = mvscript.tokenize(bytes(raw_or_text), 0)
        seq = [raw for kind, raw in toks if kind in ('ctrl', 'end')]
    else:
        seq = [v for kind, v in koenc.parse(raw_or_text) if kind == 'raw']
    return [s for s in seq if s not in MOVABLE]


def select_texts(msgs, trans, policy):
    """Return (per-message list of ('ko', text) | ('raw', bytes), report)."""
    out, rep = [], {'translated': 0, 'source_kept': 0, 'ineligible_used': [], 'kept_by_decision': []}
    for m in msgs:
        e = trans.get(m['id'])
        if e is not None and e.get('src') != m['raw']:
            raise BuildError('message %d: translation baseline %s != source %s' % (m['id'], e.get('src'), m['raw']))
        if e is not None and e.get('keep_source'):
            # recorded exception: the source bytes are the intended output
            if policy == 'release' and e.get('state') != 'distribution_eligible':
                raise BuildError('message %d keep_source is %s; release needs distribution_eligible' % (m['id'], e.get('state')))
            out.append(('raw', bytes.fromhex(m['raw'])))
            rep['kept_by_decision'].append(m['id'])
            continue
        ko = e.get('ko') if e else None
        if ko:
            if policy == 'release' and e.get('state') != 'distribution_eligible':
                raise BuildError('message %d is %s; release policy needs distribution_eligible' % (m['id'], e.get('state')))
            if e.get('state') != 'distribution_eligible':
                rep['ineligible_used'].append(m['id'])
            if protected_sequence(bytes.fromhex(m['raw'])) != protected_sequence(ko):
                raise BuildError('message %d: protected control sequence changed' % m['id'])
            lp = layout_problems(m['id'], m['raw'], ko)
            if lp:
                raise BuildError('message %d: %s' % (m['id'], lp[0]))
            if LAYOUT.get(m['id']) == 'item':
                ko = ko.replace(' ', '\u3000')   # menu renderer: no half-space control
            out.append(('ko', ko))
            rep['translated'] += 1
        else:
            if policy == 'release':
                raise BuildError('message %d has no translation' % m['id'])
            out.append(('raw', bytes.fromhex(m['raw'])))
            rep['source_kept'] += 1
    return out, rep


def build_charmap(texts):
    freq = koenc.count_chars(texts)
    return koenc.allocate(freq, ONE_BYTE_SLOTS, PAGE_ORDER, fixed=dict(FIXED, **NAME_FIXED),
                          reserved=RESERVED_GLYPHS)


def encode_script(selected, cmap):
    parts = [koenc.encode(v, cmap) if kind == 'ko' else v for kind, v in selected]
    return parts, b''.join(parts) + b'\xff'


def check_boundaries(rom_out, parts):
    """Simulate the patched SA-1 builder over the relocated script."""
    L = rom_out[mvscript.BUILDER_LEN:mvscript.BUILDER_LEN + 0x100]
    A = rom_out[mvscript.BUILDER_FE_LEN:mvscript.BUILDER_FE_LEN + 0x100]
    p, starts = NEW_SCRIPT, [NEW_SCRIPT]
    while rom_out[p] != 0xFF:
        b, arg = rom_out[p], rom_out[p + 1]
        p += L[max(b, 0xF2)]
        if b in (0xFA, 0xFB):
            starts.append(p)
        elif b == 0xFE:
            p += A[arg]
    want, q = [], NEW_SCRIPT
    for part in parts:
        want.append(q)
        q += len(part)
    want.append(q)
    if starts != want or p != q:
        bad = next(i for i, (a, b) in enumerate(zip(starts, want)) if a != b) if starts != want else -1
        raise BuildError('builder boundary mismatch at message %d' % bad)
    if len(starts) > (0x10000 - 0xDBE0) // 3:
        raise BuildError('too many messages for the BW-RAM pointer table')


def font_writes(plan, cmap, bdf):
    for ch, code in sorted(NAME_FIXED.items(), key=lambda kv: kv[1]):
        plan.patch('name glyph %s' % ch, KANA_FONT + code[0] * 64, kfont.glyph_bytes(ch, bdf))
    for ch, code in sorted(cmap.items(), key=lambda kv: kv[1]):
        if ch in FIXED or ch in NAME_FIXED:
            continue
        g = bytes(64) if ch == DRAWN_BLANK else kfont.glyph_bytes(ch, bdf)
        if len(code) == 1:
            plan.patch('glyph %s' % ch, KANA_FONT + code[0] * 64, g)
        else:
            page = PAGE_ORDER.index('%02X' % code[0])
            plan.patch('glyph %s' % ch, NEW_KANJI + (page * 256 + code[1]) * 64, g)
    for code, ch in RESERVED_GLYPHS.items():
        page = PAGE_ORDER.index('%02X' % code[0])
        plan.patch('reserved glyph %s' % ch, NEW_KANJI + (page * 256 + code[1]) * 64, kfont.glyph_bytes(ch, bdf))
    for code, ch in REDRAW.items():
        plan.patch('glyph %s' % ch, KANA_FONT + code * 64, kfont.glyph_bytes(ch, bdf, align='left'))


def lz_offset(ptr):
    return ((ptr >> 16) - 0xC0) << 16 | (ptr & 0xFFFF)


def logo_writes(plan, src):
    """Korean title logo (D11): new tiles/map assets + palette 7."""
    def ptr(i):
        return src[LZ_PTR_BANK + i] << 16 | src[LZ_PTR_HI + i] << 8 | src[LZ_PTR_LO + i]
    m56 = lz2.decompress(src, lz_offset(ptr(LOGO_MAP_ASSET)))
    orig = [m56[2 * i] | m56[2 * i + 1] << 8 for i in range(len(m56) // 2)]
    tiles, mp, pal, ntiles = title_logo.build(LOGO_IMAGE, orig)
    old_tiles = lz2.decompress(src, lz_offset(ptr(LOGO_TILES_ASSET)))
    if len(tiles) != len(old_tiles) or len(mp) != len(m56):
        raise BuildError('logo asset sizes differ from the originals')
    obj = lz2.decompress(src, lz_offset(ptr(TITLE_OBJ_ASSET)))
    obj_new = title_sub.patch_asset(obj, TITLE_SUBTITLE)
    imap = lz2.decompress(src, lz_offset(ptr(INTRO_MAP_ASSET)))
    sheet, imap_new, _ = intro_text.build(imap, intro_text.load_lines(), kfont.load_bdf())
    old_sheet = b''.join(lz2.decompress(src, lz_offset(ptr(a))) for a in INTRO_SHEET_ASSETS)
    if len(old_sheet) != len(sheet):
        raise BuildError('intro sheet size differs from the originals')
    jp_pool = mvscript.render(mvscript.tokenize(src, mvscript.builder_boundaries(src)[0][2972])[0],
                              mvscript.load_table())[:192]
    menu = lz2.decompress(src, lz_offset(ptr(ui_pool.MENU_MAP_ASSET)))
    menu_new = ui_pool.apply_map(menu, jp_pool, ui_pool.load())
    for off, data in ui_pool.rom_writes(src, jp_pool, ui_pool.load(), lorom_to_file).items():
        plan.patch('menu table', off, data, expect=src[off:off + len(data)])
    assets = [(ui_pool.MENU_MAP_ASSET, menu_new), (LOGO_TILES_ASSET, tiles), (LOGO_MAP_ASSET, mp), (TITLE_OBJ_ASSET, obj_new), (INTRO_MAP_ASSET, imap_new)]
    assets += [(a, sheet[i * 4096:(i + 1) * 4096]) for i, a in enumerate(INTRO_SHEET_ASSETS)]
    for a, off in ((poster_title.TILES_ASSET, poster_title.TILES_OFFSET), (poster_title.MAP_ASSET, poster_title.MAP_OFFSET)):
        if lz_offset(ptr(a)) != off:
            raise BuildError('poster asset %d is not at %X' % (a, off))
    poster = poster_title.build(lz2.decompress(src, poster_title.TILES_OFFSET), lz2.decompress(src, poster_title.MAP_OFFSET))
    assets.append((poster_title.TILES_ASSET, poster))
    assets += sorted(scene_text.apply_all(src).items())
    credit_sheet, credit_map = credits_text.build(lz2.decompress(src, lz_offset(ptr(credits_text.SHEET_ASSET))),
                                                  lz2.decompress(src, lz_offset(ptr(credits_text.MAP_ASSET))))
    assets += [(credits_text.SHEET_ASSET, credit_sheet), (credits_text.MAP_ASSET, credit_map)]
    assets.append((lift_label.ASSET, lift_label.build(lz2.decompress(src, lz_offset(ptr(lift_label.ASSET))))))
    riddle_tiles, riddle_writes = riddle_text.build(src)
    assets.append((riddle_text.TILE_ASSET, riddle_tiles))
    for off, data in sorted(riddle_writes.items()):
        plan.patch('riddle pieces', off, data, expect=src[off:off + len(data)])
    if len({a for a, _ in assets}) != len(assets):
        raise BuildError('an LZ asset is rewritten twice')
    at = ASSET_AREA
    for asset, raw in assets:
        comp = lz2.compress(raw)
        if lz2.decompress(comp) != raw:
            raise BuildError('LZ round trip failed for asset %d' % asset)
        plan.patch('lz asset %d' % asset, at, comp)
        p = 0xC00000 | at
        for table, byte in ((LZ_PTR_LO, p & 0xFF), (LZ_PTR_HI, p >> 8 & 0xFF), (LZ_PTR_BANK, p >> 16)):
            plan.patch('lz ptr %d' % asset, table + asset, bytes([byte]), expect=src[table + asset:table + asset + 1])
        at += len(comp)
    plan.patch('logo palette', LOGO_PALETTE, pal, expect=src[LOGO_PALETTE:LOGO_PALETTE + len(pal)])
    return ntiles


def checksum(rom):
    s = sum(rom) & 0xFFFF
    return s


def build(src, trans, policy='dev', bdf=None):
    if hashlib.sha256(src).hexdigest() != SOURCE_SHA256:
        raise BuildError('unsupported source ROM')
    msgs, _ = mvscript.extract(src)
    pool_doc = ui_pool.load()
    if 2972 not in trans:
        trans = dict(trans)
        trans[2972] = {'id': 2972, 'src': msgs[2972]['raw'], 'ko': ''.join(pool_doc['slots']) + '<FB>',
                       'state': 'needs_human_review'}
    selected, rep = select_texts(msgs, trans, policy)
    cmap = build_charmap([v for kind, v in selected if kind == 'ko'])
    parts, blob = encode_script(selected, cmap)
    if len(blob) > NEW_KANJI - NEW_SCRIPT:
        raise BuildError('script %X bytes does not fit before the kanji font' % len(blob))

    plan = WritePlan(src, size=OUT_SIZE, fill=0xFF)
    plan.protect('header', 0x7FB0, 0x7FDC)
    plan.protect('vectors', 0x7FE0, 0x8000)
    for owner, addr, expect, new in CODE_PATCHES:
        plan.patch(owner, lorom_to_file(addr), new, expect=expect)
    plan.patch('script', NEW_SCRIPT, blob)
    font_writes(plan, cmap, bdf or kfont.load_bdf())

    rep_logo = logo_writes(plan, src)
    shout = big_shout.build(kfont.load_bdf())
    for off, data in sorted(panel_gfx.build(src).items()):
        plan.patch('panel label', off, data, expect=src[off:off + 32])
    bub = bubble_gfx.build(src)
    plan.patch('hint bubbles', bubble_gfx.BASE, bub, expect=src[bubble_gfx.BASE:bubble_gfx.BASE + len(bub)])
    sn = small_names.build(src)
    plan.patch('status names', small_names.BASE, sn, expect=src[small_names.BASE:small_names.BASE + len(sn)])
    hl = hud_logo.build()
    plan.patch('hud logo', hud_logo.BASE, hl, expect=src[hud_logo.BASE:hud_logo.BASE + len(hl)])
    plan.patch('big shout art', big_shout.BASE, shout, expect=src[big_shout.BASE:big_shout.BASE + len(shout)])

    # checksum: compute over the output with placeholder complement/sum (FFFF/0000 sums to 0x1FE)
    plan.patch('checksum', 0x7FDC, b'\xff\xff\x00\x00', expect=src[0x7FDC:0x7FE0])
    out = bytearray(plan.apply())
    s = checksum(out)
    out[0x7FDC:0x7FE0] = ((s ^ 0xFFFF).to_bytes(2, 'little') + s.to_bytes(2, 'little'))
    if checksum(out) != s:
        raise BuildError('checksum not stable')
    out = bytes(out)
    verify(src, out, plan)
    check_boundaries(out, parts)
    rep['logo_tiles'] = rep_logo
    rep.update({'policy': policy, 'messages': len(msgs), 'glyphs': len([c for c in cmap if c not in FIXED]),
                'page_glyphs': len([c for c in cmap if len(cmap[c]) == 2]),
                'script_bytes': len(blob), 'distribution': policy == 'release' and not rep['ineligible_used']})
    return out, cmap, rep


def ips(src, out):
    """IPS patch (offsets < 16 MiB), records of at most 0xFFFF bytes."""
    data = bytearray(b'PATCH')
    i, n = 0, len(out)
    while i < n:
        if i < len(src) and out[i] == src[i]:
            i += 1
            continue
        j = i
        while j < n and j - i < 0xFFFF and not (j < len(src) and out[j] == src[j]):
            j += 1
        if i == 0x454F46:      # 'EOF' offset would terminate the patch early
            i -= 1
        data += i.to_bytes(3, 'big') + (j - i).to_bytes(2, 'big') + out[i:j]
        i = j
    data += b'EOF'
    return bytes(data)


def default_out():
    return os.path.join(ROOT, 'build', 'marvelous_ko_v%s.sfc' % VERSION)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--policy', choices=['dev', 'release'], default='dev')
    ap.add_argument('--out', default=default_out())
    a = ap.parse_args()
    with open(os.path.join(ROOT, 'rom', 'baserom.sfc'), 'rb') as f:
        src = f.read()
    try:
        out, cmap, rep = build(src, load_translations(), a.policy)
    except (BuildError, PlanError, koenc.EncodeError) as e:
        sys.exit('build failed: %s' % e)
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, 'wb') as f:
        f.write(out)
    with open(os.path.splitext(a.out)[0] + '.ips', 'wb') as f:
        f.write(ips(src, out))
    rep['version'] = VERSION
    rep['sha256'] = hashlib.sha256(out).hexdigest()
    rep['charmap'] = {ch: code.hex() for ch, code in cmap.items() if ch not in FIXED}
    with open(os.path.splitext(a.out)[0] + '.report.json', 'w', encoding='utf-8') as f:
        json.dump(rep, f, ensure_ascii=False, indent=1)
    marker = '' if rep['distribution'] else '  [NOT FOR DISTRIBUTION: %d ineligible, %d source-kept]' % (
        len(rep['ineligible_used']), rep['source_kept'])
    print('%s: %d translated, %d glyphs, script %d bytes%s' % (
        a.out, rep['translated'], rep['glyphs'], rep['script_bytes'], marker))


if __name__ == '__main__':
    main()
