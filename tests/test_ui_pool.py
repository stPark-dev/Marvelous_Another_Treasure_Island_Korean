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


def test_save_screen_header_reads_korean():
    """Save screen (SELECT) header table 98:8A49: SELECTでゲーム画面に -> SELECT로 종료."""
    import build
    src = open(ROM_PATH, 'rb').read()
    out, _, _ = build.build(src, {}, 'dev')
    slots = ui_pool.load()['slots']
    inv = {ui_pool.slot_tile(k): k for k in range(len(slots))}
    o = build.lorom_to_file(0x988A55)
    text = ''.join(slots[inv[(out[o + 2 * i] | out[o + 2 * i + 1] << 8) & 0x3FF]] for i in range(7))
    assert text == '로ㅤ종료ㅤㅤㅤ'


def test_save_confirm_prompt_reads_korean():
    """Save confirm table 98:98C8: (1)に記録していいですか？ -> (1)로 기록할까요?"""
    import build
    src = open(ROM_PATH, 'rb').read()
    out, _, _ = build.build(src, {}, 'dev')
    slots = ui_pool.load()['slots']
    inv = {ui_pool.slot_tile(k): k for k in range(len(slots))}
    o = build.lorom_to_file(0x9898C8)
    text = ''.join(slots[inv[(out[o + 2 * i] | out[o + 2 * i + 1] << 8) & 0x3FF]] for i in range(11))
    assert text == '로ㅤ기록할까요?ㅤㅤㅤ'


@pytest.mark.parametrize('addr,n,want', [
    (0x989AAF, 8, '로ㅤ기록.ㅤㅤㅤ'),    # (1)に記録しました。 after saving
    (0x989AD7, 7, '로ㅤ종료ㅤㅤㅤ'),       # SELECTでゲーム画面に after saving
    (0x9891B9, 2, '회ㅤ'),                 # (n)回め on save slots
])
def test_post_save_texts_read_korean(addr, n, want):
    import build
    src = open(ROM_PATH, 'rb').read()
    out, _, _ = build.build(src, {}, 'dev')
    slots = ui_pool.load()['slots']
    inv = {ui_pool.slot_tile(k): k for k in range(len(slots))}
    o = build.lorom_to_file(addr)
    assert ''.join(slots[inv[(out[o + 2 * i] | out[o + 2 * i + 1] << 8) & 0x3FF]] for i in range(n)) == want
