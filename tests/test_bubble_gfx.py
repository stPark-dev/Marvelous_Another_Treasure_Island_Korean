import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))

import bubble_gfx  # noqa: E402

ROM_PATH = os.path.join(ROOT, 'rom', 'baserom.sfc')
pytestmark = pytest.mark.skipif(not os.path.exists(ROM_PATH), reason='source ROM not present')


def test_strips_keep_icons_and_fit():
    rom = open(ROM_PATH, 'rb').read()
    out = bubble_gfx.build(rom)
    assert len(out) == 8 * bubble_gfx.STRIP
    for i, (icon_w, text, extra) in enumerate(bubble_gfx.PHRASES):
        a = bubble_gfx.read_strip(rom, i)
        b = bubble_gfx.read_strip(rom[:bubble_gfx.BASE] + out + rom[bubble_gfx.BASE + len(out):], i)
        for y in range(16):
            assert b[y][:icon_w] == a[y][:icon_w]
        assert any(1 in row for row in b)
        assert set(c for row in b for c in row) <= {0, 1, 2, 3}
