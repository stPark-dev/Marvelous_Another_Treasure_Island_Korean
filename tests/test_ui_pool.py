import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))

import lz2      # noqa: E402
import ui_pool  # noqa: E402
from dis65816 import lorom_to_file  # noqa: E402

ROM_PATH = os.path.join(ROOT, 'rom', 'baserom.sfc')
pytestmark = pytest.mark.skipif(not os.path.exists(ROM_PATH), reason='source ROM not present')


@pytest.fixture(scope='module')
def ctx():
    rom = open(ROM_PATH, 'rb').read()
    jp = json.load(open(os.path.join(ROOT, 'text', 'script_jp.json'), encoding='utf-8'))[2972]['jp'][:192]
    return rom, jp, ui_pool.load()


def decode(entries, slots):
    inv = {ui_pool.slot_tile(k): k for k in range(len(slots))}
    return ''.join(slots[inv[e & 0x3FF]] for e in entries)


def test_slots_full_length(ctx):
    rom, jp, doc = ctx
    assert len(doc['slots']) == len(jp) == 192


def test_map_overrides_read_korean(ctx):
    rom, jp, doc = ctx
    m = lz2.decompress(rom, 0x0E286B)
    new = ui_pool.apply_map(m, jp, doc)
    ent = [new[2 * i] | new[2 * i + 1] << 8 for i in range(len(new) // 2)]
    for ov in doc['overrides']:
        if ov['where'] == 'lz24':
            base = ov['screen'] * 1024 + ov['row'] * 32
            orig = [m[2 * i] | m[2 * i + 1] << 8 for i in range(base, base + 32)]
            idx = ui_pool.find_run(orig, jp, ov['jp'])
            assert decode([ent[base + i] for i in idx], doc['slots']) == ov['ko']


def test_rom_overrides(ctx):
    rom, jp, doc = ctx
    w = ui_pool.rom_writes(rom, jp, doc, lorom_to_file)
    for ov in doc['overrides']:
        if ov['where'] == 'rom':
            data = w[lorom_to_file(int(ov['addr'], 16))]
            ent = [data[2 * i] | data[2 * i + 1] << 8 for i in range(len(data) // 2)]
            assert decode(ent, doc['slots']) == ov['ko']
