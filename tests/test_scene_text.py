import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))

import lz2          # noqa: E402
import scene_text   # noqa: E402

ROM_PATH = os.path.join(ROOT, 'rom', 'baserom.sfc')
pytestmark = pytest.mark.skipif(not os.path.exists(ROM_PATH), reason='source ROM not present')


@pytest.fixture(scope='module')
def rom():
    return open(ROM_PATH, 'rb').read()


def load(rom, spec):
    t = lz2.decompress(rom, scene_text.asset_offset(rom, spec['tile_asset']))
    m = lz2.decompress(rom, scene_text.asset_offset(rom, spec['map_asset']))
    return t, m


def screen(m, spec):
    base = spec['map_half'] * 0x800 + spec['screen'] * 0x400
    return [m[2 * (base + i)] | m[2 * (base + i) + 1] << 8 for i in range(1024)]


@pytest.mark.parametrize('name', sorted(scene_text.SPECS))
def test_only_rebuilt_cells_and_free_tiles_change(rom, name):
    spec = scene_text.SPECS[name]
    t, m = load(rom, spec)
    nt, nm = scene_text.build(t, m, spec)
    assert len(nt) == len(t) and len(nm) == len(m)
    cells = scene_text.rebuild_cells(spec)
    a, b = screen(m, spec), screen(nm, spec)
    for i in range(1024):
        if divmod(i, 32) not in cells:
            assert a[i] == b[i]
    # map bytes outside the scene screen are untouched
    base = 2 * (spec['map_half'] * 0x800 + spec['screen'] * 0x400)
    assert nm[:base] == m[:base] and nm[base + 2048:] == m[base + 2048:]
    # tiles still shown outside the rebuilt cells keep their pixels
    lo = spec['tile_sub'] * 64
    v0, v1, h0, h1 = spec.get('visible', (0, 32, 0, 32))
    kept = {(e & 0x3FF) - 512 + lo for i, e in enumerate(a)
            if divmod(i, 32) not in cells and v0 <= i // 32 < v1 and h0 <= i % 32 < h1}
    for k in kept | set(spec.get('protect_tiles', ())):
        assert nt[k * 32:k * 32 + 32] == t[k * 32:k * 32 + 32]
    # tiles outside the uploaded window never change
    assert nt[:lo * 32] == t[:lo * 32] and nt[(lo + 128) * 32:] == t[(lo + 128) * 32:]


@pytest.mark.parametrize('name', sorted(scene_text.SPECS))
def test_text_drawn_with_allowed_colours(rom, name):
    spec = scene_text.SPECS[name]
    t, m = load(rom, spec)
    nt, nm = scene_text.build(t, m, spec)
    pix = scene_text.render_screen(nt, screen(nm, spec), spec)
    colours = {pix[y][x] for x, y in scene_text.owned_pixels(spec)}
    allowed = set(spec['bg_colours'])
    for item in spec['texts']:
        allowed |= {item['fill'], item.get('shade', item['fill']), item.get('outline'), item.get('shadow')}
    assert colours <= allowed
    assert colours - set(spec['bg_colours'])        # some text was drawn


def test_text_over_kept_cell_rejected(rom):
    spec = dict(scene_text.SPECS['camp_rules'])
    spec['texts'] = [dict(spec['texts'][0], x=152, y=32, text='가가가')]   # runs into the A icon
    t, m = load(rom, spec)
    with pytest.raises(ValueError, match='leaves the rebuilt cells'):
        scene_text.build(t, m, spec)


def test_tile_pool_exhaustion_rejected(rom):
    spec = dict(scene_text.SPECS['camp_rules'])
    spec['texts'] = [dict(spec['texts'][0], x=81, y=y, text='뷁뷁뷁뷁뷁뷁뷁뷁') for y in (16, 32, 48, 64, 80)]
    spec['rebuild'] = [(2, 12, 10, 24)]
    spec['keep'] = []
    spec['protect_tiles'] = list(range(0, 100))
    t, m = load(rom, spec)
    with pytest.raises(ValueError, match='needs more than'):
        scene_text.build(t, m, spec)


def test_apply_all_chains_specs_per_asset(rom):
    out = scene_text.apply_all(rom)
    want = {}
    for spec in scene_text.SPECS.values():
        t, m = load(rom, spec)
        t = want.get(spec['tile_asset'], t)
        m = want.get(spec['map_asset'], m)
        want[spec['tile_asset']], want[spec['map_asset']] = scene_text.build(t, m, spec)
    assert out == want
    assert len([s for s in scene_text.SPECS.values() if s['map_asset'] == 77]) >= 2   # map 77 carries two specs


def test_erase_background_removes_text_colours(rom):
    spec = dict(scene_text.SPECS['school_note'], texts=[])
    t, m = load(rom, spec)
    nt, nm = scene_text.build(t, m, spec)
    pix = scene_text.render_screen(nt, screen(nm, spec), spec)
    for r, c in scene_text.rebuild_cells(spec):
        for y in range(8):
            for x in range(8):
                assert pix[r * 8 + y][c * 8 + x] not in spec['erase']


def test_vertical_text_stays_in_one_tile_column(rom):
    spec = scene_text.SPECS['colonel_letter']
    t, m = load(rom, spec)
    nt, nm = scene_text.build(t, m, spec)
    pix = scene_text.render_screen(nt, screen(nm, spec), spec)
    for item in spec['texts']:
        assert item['vertical']
        col = item['x'] // 8
        inked = {x // 8 for y in range(256) for x in range(256)
                 if pix[y][x] == item['fill'] and item['y'] <= y < item['y'] + 8 * len(item['text'])
                 and abs(x // 8 - col) <= 1}
        assert inked == {col}


def test_clear_boxes_define_rebuilt_cells():
    spec = scene_text.SPECS['taunt_note']
    cells = scene_text.rebuild_cells(spec)
    for x0, y0, x1, y1 in spec['clear']:
        for y in range(y0, y1):
            for x in range(x0, x1):
                assert (y // 8, x // 8) in cells


def test_clear_keeps_pixels_outside_boxes(rom):
    spec = dict(scene_text.SPECS['taunt_note'], texts=[])
    t, m = load(rom, spec)
    nt, nm = scene_text.build(t, m, spec)
    a = scene_text.render_screen(t, screen(m, spec), spec)
    b = scene_text.render_screen(nt, screen(nm, spec), spec)
    inside = {(x, y) for x0, y0, x1, y1 in spec['clear'] for y in range(y0, y1) for x in range(x0, x1)}
    for r, c in scene_text.rebuild_cells(spec):
        for y in range(r * 8, r * 8 + 8):
            for x in range(c * 8, c * 8 + 8):
                assert b[y][x] == (spec['paper'] if (x, y) in inside else a[y][x])


def test_sign_protects_scene_2b_tiles(rom):
    """Scene 0x2B shows map 75/0 bottom-left with the same tile window (86/2): tiles 0x250-0x277."""
    spec = scene_text.SPECS['keep_out_sign']
    t, m = load(rom, spec)
    nt, _ = scene_text.build(t, m, spec)
    lo = spec['tile_sub'] * 64
    for k in range(0x50, 0x78):
        assert k + lo in spec['protect_tiles']
        assert nt[(lo + k) * 32:(lo + k + 1) * 32] == t[(lo + k) * 32:(lo + k + 1) * 32]
