import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))

import kfont      # noqa: E402
import lz2        # noqa: E402
import title_sub  # noqa: E402

ROM_PATH = os.path.join(ROOT, 'rom', 'baserom.sfc')
pytestmark = pytest.mark.skipif(not os.path.exists(ROM_PATH), reason='source ROM not present')


def test_patch_keeps_tilde_and_changes_text_tiles():
    r = open(ROM_PATH, 'rb').read()
    a = lz2.decompress(r, 0x1DA5ED)
    b = title_sub.patch_asset(a, '또 하나의 보물섬', kfont.load_bdf())
    assert len(b) == len(a)
    assert b[0:64] == a[0:64]                       # tilde tile 192/193 untouched
    o = (194 - 192) * 32
    assert b[o:o + 64] != a[o:o + 64]
    o = (226 - 192) * 32
    assert b[o:o + 64] == bytes(64)                 # TM removed
    # tiles outside the subtitle are untouched
    keep = set(range(len(a) // 32)) - {t - 192 + d for t in title_sub.TEXT_TILES + [226] for d in (0, 1, 16, 17)}
    assert all(a[k * 32:k * 32 + 32] == b[k * 32:k * 32 + 32] for k in keep)


def test_strip_fits_and_uses_palette_range():
    px = title_sub.render_strip('또 하나의 보물섬', kfont.load_bdf())
    used = {c for row in px for c in row}
    assert used <= {0, 7, 8, 9, 10, 11, 12, 13, 14, 15}
    assert any(px[y][0] for y in range(16)) is False and any(px[y][127] for y in range(16)) is False
