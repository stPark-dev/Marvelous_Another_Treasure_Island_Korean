import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))

import big_shout  # noqa: E402
import kfont      # noqa: E402


def test_build_size_and_blank_piece():
    d = big_shout.build(kfont.load_bdf())
    assert len(d) == big_shout.PIECES * 128
    assert not any(d[3 * 128:4 * 128])
    # every laid-out piece except the blank has ink
    for p in list(big_shout.LAYOUT_A) + list(big_shout.LAYOUT_B):
        if p != 3:
            assert any(d[p * 128:(p + 1) * 128]), p


def test_shared_blank_cells_are_empty_in_art():
    bdf = kfont.load_bdf()
    a, b = big_shout.art_a(bdf), big_shout.art_b(bdf)
    assert not any(a[y][x] for y in range(16) for x in range(32, 64))          # monkey col 1 row 0
    for row in (0, 2):
        assert not any(b[row * 16 + y][x] for y in range(16) for x in range(64, 96))
