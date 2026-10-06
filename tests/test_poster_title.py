import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))

import lz2           # noqa: E402
import poster_title  # noqa: E402

ROM_PATH = os.path.join(ROOT, 'rom', 'baserom.sfc')
pytestmark = pytest.mark.skipif(not os.path.exists(ROM_PATH), reason='source ROM not present')


@pytest.fixture(scope='module')
def assets():
    rom = open(ROM_PATH, 'rb').read()
    t = lz2.decompress(rom, poster_title.TILES_OFFSET)
    m = lz2.decompress(rom, poster_title.MAP_OFFSET)
    return t, m, poster_title.build(t, m)        # new tiles only; the shared map is untouched


def entries(m):
    return [m[2 * i] | m[2 * i + 1] << 8 for i in range(len(m) // 2)]


def test_sizes_kept_and_only_title_tiles_change(assets):
    t, m, nt = assets
    assert len(nt) == len(t)
    own = poster_title.title_tiles(entries(m))
    for k in range(len(t) // 32):
        if 512 + k not in own:
            assert nt[k * 32:k * 32 + 32] == t[k * 32:k * 32 + 32]
    assert any(nt[(n - 512) * 32:(n - 511) * 32] != t[(n - 512) * 32:(n - 511) * 32] for n in own)


def test_title_tiles_shown_only_in_title(assets):
    t, m, _ = assets
    ent = entries(m)
    own = poster_title.title_tiles(ent)
    assert len(own) == 2 * (poster_title.COL1 - poster_title.COL0)
    for r in poster_title.VISIBLE_ROWS:
        for c in range(32):
            if not (r in poster_title.ROWS and poster_title.COL0 <= c < poster_title.COL1):
                assert ent[poster_title.MAP_BASE + r * 32 + c] & 0x3FF not in own


def test_title_uses_poster_colours(assets):
    _, m, nt = assets
    pix = poster_title.read_rect(nt, entries(m))
    used = {c for row in pix for c in row}
    assert used <= {poster_title.BG, poster_title.FILL, poster_title.RED, poster_title.GREEN}
    assert {poster_title.FILL, poster_title.RED, poster_title.GREEN} <= used


def test_too_long_text_rejected(assets):
    t, m, _ = assets
    with pytest.raises(ValueError):
        poster_title.build(t, m, [('가' * 12, poster_title.RED)])
