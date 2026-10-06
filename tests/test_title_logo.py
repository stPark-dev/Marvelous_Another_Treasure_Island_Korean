import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))

import lz2         # noqa: E402
import title_logo  # noqa: E402

ROM_PATH = os.path.join(ROOT, 'rom', 'baserom.sfc')
LOGO = os.path.join(ROOT, 'title_ko.png')
pytestmark = pytest.mark.skipif(not (os.path.exists(ROM_PATH) and os.path.exists(LOGO)), reason='inputs missing')


@pytest.fixture(scope='module')
def built():
    r = open(ROM_PATH, 'rb').read()
    m56 = lz2.decompress(r, 0x123726)
    orig = [m56[2 * i] | m56[2 * i + 1] << 8 for i in range(512)]
    return title_logo.build(LOGO, orig), orig


def test_sizes_and_budget(built):
    (tiles, mp, pal, n), _ = built
    assert len(tiles) == 8192 and len(mp) == 1024 and len(pal) == 28
    assert n <= 256


def test_map_renders_back_to_quantized_image(built):
    (tiles, mp, pal, n), orig = built
    idx, pal = title_logo.quantize(title_logo.prepare(LOGO, width=232))
    idx = title_logo.reduce_tiles(idx, 255, [(0, 0, 0)] + list(pal) + [title_logo.WHITE])
    ents = [mp[2 * i] | mp[2 * i + 1] << 8 for i in range(512)]
    for ty in range(16):
        for tx in range(32):
            e = ents[ty * 32 + tx]
            want = title_logo.tile_bytes(idx, tx, ty)
            if (e >> 10) & 7 != 7:
                assert want == bytes(32)
                assert (orig[ty * 32 + tx] >> 10) & 7 != 7 or e == 0
                continue
            t = tiles[((e & 0x3FF) - 512) * 32:((e & 0x3FF) - 512 + 1) * 32]
            got = next(v for v, h, vf in title_logo.flips(t) if (h, vf) == ((e >> 14) & 1, (e >> 15) & 1))
            assert got == want
