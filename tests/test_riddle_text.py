import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))

import lz2           # noqa: E402
import riddle_text   # noqa: E402
import scene_text    # noqa: E402

ROM_PATH = os.path.join(ROOT, 'rom', 'baserom.sfc')
pytestmark = pytest.mark.skipif(not os.path.exists(ROM_PATH), reason='source ROM not present')


@pytest.fixture(scope='module')
def rom():
    return open(ROM_PATH, 'rb').read()


@pytest.fixture(scope='module')
def result(rom):
    return riddle_text.build(rom)


def patched(rom, writes):
    out = bytearray(rom)
    for off, data in writes.items():
        out[off:off + len(data)] = data
    return bytes(out)


def grid(rom):
    """12x10 composed map entries for scene 54."""
    ids = [rom[riddle_text.ID_LIST + 2 * i] | rom[riddle_text.ID_LIST + 2 * i + 1] << 8 for i in range(30)]
    cells = [[0] * 12 for _ in range(10)]
    for k, pid in enumerate(ids):
        pr, pc = divmod(k, 6)
        p = riddle_text.PIECES + pid * 8
        e = [rom[p + 2 * j] | rom[p + 2 * j + 1] << 8 for j in range(4)]
        cells[pr * 2][pc * 2], cells[pr * 2][pc * 2 + 1], cells[pr * 2 + 1][pc * 2], cells[pr * 2 + 1][pc * 2 + 1] = e
    return cells


def test_writes_stay_in_riddle_tables(rom, result):
    _, writes = result
    lo_p = riddle_text.PIECES + min(riddle_text.OWN_PIECES) * 8
    hi_p = riddle_text.PIECES + (max(riddle_text.OWN_PIECES) + 1) * 8
    for off, data in writes.items():
        in_ids = riddle_text.ID_LIST <= off and off + len(data) <= riddle_text.ID_LIST + 60
        in_pieces = lo_p <= off and off + len(data) <= hi_p
        assert in_ids or in_pieces
    assert riddle_text.OWN_PIECES == list(range(0x1CE, 0x1DD))


def test_only_riddle_tiles_change(rom, result):
    tiles, _ = result
    old = lz2.decompress(rom, scene_text.asset_offset(rom, riddle_text.TILE_ASSET))
    assert len(tiles) == len(old)
    for k in range(len(old) // 32):
        if k not in riddle_text.FREE_TILES:
            assert tiles[k * 32:k * 32 + 32] == old[k * 32:k * 32 + 32]


def test_composed_grid_puts_glyphs_in_original_columns(rom, result):
    _, writes = result
    cells = grid(patched(rom, writes))
    glyph_tiles = {512 + t for t in riddle_text.FREE_TILES}
    cols = {c for r in range(10) for c in range(12) if cells[r][c] & 0x3FF in glyph_tiles}
    assert cols == {1, 4, 7, 10}                     # map cols 8, 11, 14, 17
    for r in range(10):
        for c in range(12):
            assert cells[r][c] & ~0x3FF == 0x1C00    # palette 7, priority as before


def test_column_text_matches_layout(rom, result):
    _, writes = result
    cells = grid(patched(rom, writes))
    tile_of = riddle_text.glyph_tiles()
    for col, text in riddle_text.COLUMNS:
        for pr, ch in enumerate(text):
            top, bottom = cells[pr * 2][col] & 0x3FF, cells[pr * 2 + 1][col] & 0x3FF
            if ch == ' ':
                assert top - 512 not in riddle_text.FREE_TILES
            else:
                assert (top - 512, bottom - 512) == tile_of[ch]


def test_glyph_masks_fit_one_tile_column():
    for ch in set(''.join(t for _, t in riddle_text.COLUMNS)) - {' '}:
        m = riddle_text.glyph_mask(ch)
        assert len(m) <= 14 and all(len(row) <= 7 for row in m)
        assert any('#' in row for row in m)
