import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))

import credits_text  # noqa: E402
import lz2           # noqa: E402
import scene_text    # noqa: E402

ROM_PATH = os.path.join(ROOT, 'rom', 'baserom.sfc')
pytestmark = pytest.mark.skipif(not os.path.exists(ROM_PATH), reason='source ROM not present')


@pytest.fixture(scope='module')
def rom():
    return open(ROM_PATH, 'rb').read()


@pytest.fixture(scope='module')
def assets(rom):
    sheet = lz2.decompress(rom, scene_text.asset_offset(rom, credits_text.SHEET_ASSET))
    cmap = lz2.decompress(rom, scene_text.asset_offset(rom, credits_text.MAP_ASSET))
    return sheet, cmap, credits_text.build(sheet, cmap)


def test_source_decodes_to_known_credits(assets):
    _, cmap, _ = assets
    rows = credits_text.decode(cmap)
    assert rows[0].strip('　') == 'グラフィック'
    assert rows[44].strip('　') == 'エクゼクティブ　プロデューサー'
    assert rows[31].strip('　') == '坂本　哲哉　　西田　勝　　　SMCデバックチーム'


def test_titles_become_korean_and_names_stay(assets):
    sheet, cmap, (new_sheet, new_map) = assets
    new_rows = credits_text.decode(new_map, credits_text.glyph_chars(cmap))
    for row in range(credits_text.ROWS):
        if row in credits_text.TITLES:
            assert new_rows[row].strip('　') == credits_text.TITLES[row]
        else:
            assert new_map[row * 64:row * 64 + 64] == cmap[row * 64:row * 64 + 64]
    assert new_map[credits_text.ROWS * 64:] == cmap[credits_text.ROWS * 64:]


def test_name_glyphs_untouched(assets):
    sheet, cmap, (new_sheet, _) = assets
    for g in credits_text.name_glyphs(cmap):
        for tn in credits_text.glyph_tiles(g):
            assert new_sheet[tn * 16:tn * 16 + 16] == sheet[tn * 16:tn * 16 + 16]


def test_titles_are_centred(assets):
    _, _, (_, new_map) = assets
    for row, text in credits_text.TITLES.items():
        cols = [c for c in range(32) if (new_map[row * 64 + 2 * c] | new_map[row * 64 + 2 * c + 1] << 8) & 0x3FF
                != credits_text.BLANK]
        assert cols[0] == (32 - len(text)) // 2 and cols[-1] == cols[0] + len(text) - 1


def test_korean_glyphs_use_outline_style(assets):
    sheet, cmap, (new_sheet, _) = assets
    changed = [g for g in range(128) if any(new_sheet[t * 16:t * 16 + 16] != sheet[t * 16:t * 16 + 16]
                                            for t in credits_text.glyph_tiles(g))]
    assert changed
    for g in changed:
        px = credits_text.glyph_pixels(new_sheet, g)
        assert {v for row in px for v in row} == {0, 1, 2}
        assert not any(px[0]) and not any(px[15]) and not any(row[0] or row[15] for row in px)
