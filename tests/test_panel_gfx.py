import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))

import panel_gfx  # noqa: E402

ROM_PATH = os.path.join(ROOT, 'rom', 'baserom.sfc')
pytestmark = pytest.mark.skipif(not os.path.exists(ROM_PATH), reason='source ROM not present')


def test_only_label_area_changes():
    rom = open(ROM_PATH, 'rb').read()
    tiles = panel_gfx.build(rom)
    patched = bytearray(rom)
    for off, data in tiles.items():
        patched[off:off + 32] = data
    x0, y0, x1, y1 = panel_gfx.AREA
    for sheet, face, body, edge in panel_gfx.VARIANTS:
      for name, ts in panel_gfx.PANELS.items():
        a = panel_gfx.read_panel(rom, ts, sheet)
        b = panel_gfx.read_panel(bytes(patched), ts, sheet)
        for y in range(32):
            for x in range(32):
                if not (x0 <= x <= x1 and y0 <= y <= y1):
                    assert a[y][x] == b[y][x]
        assert any(b[y][x] == body for y in range(y0, y1 + 1) for x in range(x0, x1 + 1))
    assert len(tiles) == 2 * 2 * 16
