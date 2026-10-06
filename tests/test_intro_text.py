import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))

import intro_text  # noqa: E402
import kfont       # noqa: E402
import lz2         # noqa: E402

ROM_PATH = os.path.join(ROOT, 'rom', 'baserom.sfc')
pytestmark = pytest.mark.skipif(not os.path.exists(ROM_PATH), reason='source ROM not present')


@pytest.fixture(scope='module')
def built():
    r = open(ROM_PATH, 'rb').read()
    mp = lz2.decompress(r, 0x1257F6)
    lines = intro_text.load_lines()
    return mp, lines, intro_text.build(mp, lines, kfont.load_bdf())


def test_sizes_and_budget(built):
    mp, lines, (sheet, newmap, used) = built
    assert len(sheet) == 12288 and len(newmap) == len(mp) == 4096
    assert used <= intro_text.CELLS - 1


def test_every_line_readable_back(built):
    mp, lines, (sheet, newmap, used) = built
    ent = [newmap[2 * i] | newmap[2 * i + 1] << 8 for i in range(2048)]
    bdf = kfont.load_bdf()
    for ln in lines:
        text = ln['ko']
        start = ln['half'] * 16 + (16 - len(text)) // 2
        for i, ch in enumerate(text):
            if ch == ' ':
                continue
            n = ent[ln['row'] * 32 + start + i] & 0x3FF
            want = intro_text.cell_bytes(intro_text.glyph_cell(ch, bdf))
            assert sheet[n * 16:n * 16 + 16] == want[0]
            assert sheet[(n + 17) * 16:(n + 17) * 16 + 16] == want[3]


def test_lines_fit_and_only_original_rows_change(built):
    mp, lines, (sheet, newmap, used) = built
    rows = {(l['row'], l['half']) for l in lines} | {(l['copy_to'][1], l['copy_to'][0]) for l in lines if 'copy_to' in l}
    for r in range(64):
        for c in range(32):
            if (r, c // 16) not in rows:
                assert newmap[2 * (r * 32 + c):2 * (r * 32 + c) + 2] == mp[2 * (r * 32 + c):2 * (r * 32 + c) + 2]
