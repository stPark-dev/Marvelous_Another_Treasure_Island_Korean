"""Menu glyph pool (message 2972) and its static consumers.

The pool is drawn as a 16x16-glyph sheet; slot k is BG tile (k//8)*0x20 +
(k%8)*2.  Game code composes some screens from slot positions, so the Korean
pool keeps each slot's meaning (data/ui_pool.json "slots").  Static tilemap
entries whose Japanese words share slots in conflicting ways are rewritten to
other slots ("overrides"): runs in the menu BG2 map (LZ asset 24, 64x64 entries
as four 32x32 screens) or tile-word tables in ROM.
"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MENU_MAP_ASSET = 24
BLANK = '　'


def slot_tile(k):
    return (k // 8) * 0x20 + (k % 8) * 2


def load(path=None):
    with open(path or os.path.join(ROOT, 'data', 'ui_pool.json'), encoding='utf-8') as f:
        return json.load(f)


def slot_of(slots):
    """char -> slot for override lookups: the last occurrence, because screens
    such as name entry reuse the top rows of the sheet buffer for other glyphs
    while the bottom rows keep the pool."""
    out = {}
    for k, ch in enumerate(slots):
        out[ch] = k
    return out


def find_run(entries, jp_pool, jp):
    """Indices of a run of palette-4 pool entries spelling jp (in order)."""
    inv = {slot_tile(k): k for k in range(len(jp_pool))}
    cand = [i for i, e in enumerate(entries) if (e >> 10) & 7 == 4 and (e & 0x3FF) in inv]
    text = ''.join(jp_pool[inv[entries[i] & 0x3FF]] for i in cand)
    p = text.find(jp)
    if p < 0:
        raise ValueError('run %r not found' % jp)
    return cand[p:p + len(jp)]


def rewrite(entries, idx, ko, slots):
    so = slot_of(slots)
    if len(idx) != len(ko):
        raise ValueError('override %r must keep length %d' % (ko, len(idx)))
    out = list(entries)
    for i, ch in zip(idx, ko):
        if ch not in so:
            raise ValueError('override char %r is not in the pool' % ch)
        out[i] = (entries[i] & 0xFC00) | slot_tile(so[ch])
    return out


def apply_map(map_bytes, jp_pool, doc):
    ent = [map_bytes[2 * i] | map_bytes[2 * i + 1] << 8 for i in range(len(map_bytes) // 2)]
    for ov in doc['overrides']:
        if ov['where'] != 'lz24':
            continue
        base = ov['screen'] * 1024 + ov['row'] * 32
        row = ent[base:base + 32]
        idx = find_run(row, jp_pool, ov['jp'])
        row = rewrite(row, idx, ov['ko'], doc['slots'])
        ent[base:base + 32] = row
    return b''.join(e.to_bytes(2, 'little') for e in ent)


def rom_writes(rom, jp_pool, doc, to_file):
    """{file offset: new bytes} for ROM tile-word tables."""
    out = {}
    inv = {slot_tile(k): k for k in range(len(jp_pool))}
    for ov in doc['overrides']:
        if ov['where'] != 'rom':
            continue
        off = to_file(int(ov['addr'], 16))
        n = len(ov['jp'])
        ent = [rom[off + 2 * i] | rom[off + 2 * i + 1] << 8 for i in range(n)]
        got = ''.join(jp_pool[inv[e & 0x3FF]] if (e & 0x3FF) in inv else '?' for e in ent)
        if got != ov['jp']:
            raise ValueError('ROM table at %s reads %r, expected %r' % (ov['addr'], got, ov['jp']))
        new = rewrite(ent, list(range(n)), ov['ko'], doc['slots'])
        out[off] = b''.join(e.to_bytes(2, 'little') for e in new)
    return out
