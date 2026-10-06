import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))

import small_names  # noqa: E402

ROM_PATH = os.path.join(ROOT, 'rom', 'baserom.sfc')
pytestmark = pytest.mark.skipif(not os.path.exists(ROM_PATH), reason='source ROM not present')


def test_only_name_boxes_change():
    rom = open(ROM_PATH, 'rb').read()
    out = small_names.build(rom)
    patched = rom[:small_names.BASE] + out + rom[small_names.BASE + len(out):]
    a, b = small_names.read(rom), small_names.read(patched)
    for y in range(16):
        assert a[y][72:] == b[y][72:]
    for x0, _ in small_names.BOXES:
        assert any(b[y][x0 + x] == 2 for y in range(16) for x in range(24))
