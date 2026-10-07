import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))

import dud_sign     # noqa: E402
import lz2          # noqa: E402
import scene_text   # noqa: E402

ROM_PATH = os.path.join(ROOT, 'rom', 'baserom.sfc')
pytestmark = pytest.mark.skipif(not os.path.exists(ROM_PATH), reason='source ROM not present')


@pytest.fixture(scope='module')
def tiles():
    rom = open(ROM_PATH, 'rb').read()
    old = lz2.decompress(rom, scene_text.asset_offset(rom, dud_sign.ASSET))
    return old, dud_sign.build(old)


def test_only_the_dud_tiles_change(tiles):
    old, new = tiles
    assert len(new) == len(old)
    changed = {k for k in range(len(old) // 32) if old[k * 32:k * 32 + 32] != new[k * 32:k * 32 + 32]}
    assert changed and changed <= {k for row in dud_sign.GRID for k in row}


def test_text_colours_and_background(tiles):
    old, new = tiles
    before = dud_sign.read(old)
    after = dud_sign.read(new)
    bg = {v for row in before for v in row} - set(dud_sign.ERASE)
    assert {v for row in after for v in row} <= bg | {dud_sign.STROKE, dud_sign.EDGE}
    assert sum(row.count(dud_sign.STROKE) for row in after) > 40


def test_source_is_the_katakana(tiles):
    old, _ = tiles
    px = dud_sign.read(old)
    assert px[3][:8] == [7] * 8                  # top bar of ス
