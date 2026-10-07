import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))

import inline_icons  # noqa: E402

ROM_PATH = os.path.join(ROOT, 'rom', 'baserom.sfc')
pytestmark = pytest.mark.skipif(not os.path.exists(ROM_PATH), reason='source ROM not present')


@pytest.fixture(scope='module')
def rom():
    return open(ROM_PATH, 'rb').read()


def test_only_icon_tiles_written(rom):
    writes = inline_icons.build(rom)
    allowed = {base + row * inline_icons.ROW + col * 16
               for base in inline_icons.ICONS for row in range(2) for col in range(4)}
    assert set(writes) == allowed
    assert all(len(d) == 16 for d in writes.values())


@pytest.mark.parametrize('base', sorted(inline_icons.ICONS))
def test_frame_kept_and_text_drawn(rom, base):
    old = inline_icons.read_icon(rom, base)
    out = bytearray(rom)
    for off, data in inline_icons.build(rom).items():
        out[off:off + 16] = data
    new = inline_icons.read_icon(bytes(out), base)
    for y in range(16):
        for x in range(32):
            if y in (0, 1, 15) or x in (0, 31):
                assert new[y][x] == old[y][x]
    inner = {new[y][x] for y in range(2, 15) for x in range(1, 31)}
    assert inner == {inline_icons.BG, inline_icons.TEXT, inline_icons.EDGE}
    assert new != old


def test_source_icons_are_the_japanese_labels(rom):
    team = inline_icons.read_icon(rom, 0x26E6C0)
    assert team[1][1:31] == [2] * 30          # white top rule of the frame
    assert inline_icons.ICONS == {0x26E6C0: '팀워크', 0x26E880: '아이템'}
