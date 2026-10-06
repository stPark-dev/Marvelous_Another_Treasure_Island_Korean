import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))

import lift_label   # noqa: E402
import lz2          # noqa: E402
import scene_text   # noqa: E402

ROM_PATH = os.path.join(ROOT, 'rom', 'baserom.sfc')
pytestmark = pytest.mark.skipif(not os.path.exists(ROM_PATH), reason='source ROM not present')


@pytest.fixture(scope='module')
def tiles():
    rom = open(ROM_PATH, 'rb').read()
    old = lz2.decompress(rom, scene_text.asset_offset(rom, lift_label.ASSET))
    return old, lift_label.build(old)


def test_only_label_copies_change(tiles):
    old, new = tiles
    assert len(new) == len(old)
    changed = {k for k in range(len(old) // 32) if old[k * 32:k * 32 + 32] != new[k * 32:k * 32 + 32]}
    assert changed == set(lift_label.UP_TILES) | set(lift_label.DOWN_TILES)


def test_copies_identical_and_two_colours(tiles):
    _, new = tiles
    for group in (lift_label.UP_TILES, lift_label.DOWN_TILES):
        first = new[group[0] * 32:group[0] * 32 + 32]
        assert all(new[k * 32:k * 32 + 32] == first for k in group)
        px = scene_text._tile_pixels(new, group[0])
        assert {v for row in px for v in row} == {lift_label.BG, lift_label.INK}


def test_source_tiles_are_the_kanji(tiles):
    old, _ = tiles
    assert scene_text._tile_pixels(old, lift_label.UP_TILES[0])[6] == [1, 10, 10, 10, 10, 10, 10, 1]   # 上 base stroke
