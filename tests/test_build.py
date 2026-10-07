import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))

import build      # noqa: E402
import mvscript   # noqa: E402

ROM_PATH = os.path.join(ROOT, 'rom', 'baserom.sfc')
pytestmark = pytest.mark.skipif(not os.path.exists(ROM_PATH), reason='source ROM not present')


@pytest.fixture(scope='module')
def src():
    with open(ROM_PATH, 'rb') as f:
        return f.read()


@pytest.fixture(scope='module')
def msgs(src):
    return mvscript.extract(src)[0]


def entry(msgs, i, ko, state='in_progress'):
    return {i: {'id': i, 'src': msgs[i]['raw'], 'ko': ko, 'state': state}}


def test_untranslated_build_relocates_script_verbatim(src):
    msgs, _ = mvscript.extract(src)
    keep = {2972: {'id': 2972, 'src': msgs[2972]['raw'], 'ko': '', 'keep_source': True, 'state': 'needs_review'}}
    out, cmap, rep = build.build(src, keep, 'dev')       # menu pool is otherwise generated
    _, end = mvscript.builder_boundaries(src)
    script = src[mvscript.SCRIPT_START:end + 1]
    assert len(out) == 0x400000
    assert out[0x300000:0x300000 + len(script)] == script
    assert rep['translated'] == 0 and rep['page_glyphs'] == 0
    s = sum(out) & 0xFFFF
    assert out[0x7FDE] | out[0x7FDF] << 8 == s
    assert (out[0x7FDC] | out[0x7FDD] << 8) ^ s == 0xFFFF


def test_translated_message_encodes_and_places_glyphs(src, msgs):
    ko = '우리 원숭이들은 대대로 이 섬의<F8>\n비밀을 지키는 종족이니라.[F9][FE69][F6]그리고 오늘, 마침내 그 역할이[F6]네게 돌아왔느니라.[F6]<FA>'
    out, cmap, rep = build.build(src, entry(msgs, 1571, ko), 'dev')
    assert rep['translated'] == 2          # message 1571 + the generated menu pool 2972
    code = cmap['이']
    assert len(code) == 1 and out[0x2AC000 + code[0] * 64:0x2AC000 + code[0] * 64 + 64] != src[0x2AC000 + code[0] * 64:0x2AC000 + code[0] * 64 + 64]
    assert not rep['distribution']


def test_protected_control_change_fails(src, msgs):
    ko = '우리<F8>\n비밀[F9][F6]그리고[F6]네게[F6]<FA>'   # FE69 dropped
    with pytest.raises(build.BuildError):
        build.build(src, entry(msgs, 1571, ko), 'dev')


def test_moving_line_and_page_breaks_is_allowed(src, msgs):
    ko = '우리 원숭이들은[F9]대대로<F8>\n이 섬의 비밀을<F8>\n지키느니라.[FE69][F6]그리고[F6]네게[F6]<FA>'
    build.build(src, entry(msgs, 1571, ko), 'dev')


def test_overlong_line_fails(src, msgs):
    ko = '가' * 23 + '[FE69][F6]가[F6]가[F6]<FA>'
    with pytest.raises(build.BuildError):
        build.build(src, entry(msgs, 1571, ko), 'dev')


def test_stale_baseline_fails(src, msgs):
    e = entry(msgs, 1571, '가[FE69][F6][F6][F6]<FA>')
    e[1571]['src'] = 'fa'
    with pytest.raises(build.BuildError):
        build.build(src, e, 'dev')


def test_release_policy_rejects_missing_and_ineligible(src, msgs):
    with pytest.raises(build.BuildError):
        build.build(src, {}, 'release')


def test_blit_entry_normalizes_odd_column(src):
    """9F:BF97 must call the helper that skips the bottom-tile half (half-space alignment)."""
    out, _, _ = build.build(src, {}, 'dev')
    entry = build.lorom_to_file(0x9FBF97)
    assert out[entry] == 0x20                      # JSR
    helper = 0x9F0000 | int.from_bytes(out[entry + 1:entry + 3], 'little')
    h = build.lorom_to_file(helper)
    assert out[h:h + len(build.BLIT_FIX_CODE)] == build.BLIT_FIX_CODE
    assert build.BLIT_FIX_CODE.endswith(b'\xa0\x00\x00\x60')   # original LDY #0 then RTS


def test_name_entry_syllables_fixed_to_one_byte_slots(src):
    import json
    ne = json.load(open(os.path.join(ROOT, 'data', 'name_entry.json'), encoding='utf-8'))
    out, cmap, _ = build.build(src, {}, 'dev')
    assert cmap[ne['page0'][0]] == b'\x00'
    assert cmap[ne['page1'][0]] == b'\x50'
    assert cmap[ne['e9_ef'][0]] == b'\xe9'
    # glyph for slot 0 is the Korean syllable, even with no translation selected
    g = build.kfont.glyph_bytes(ne['page0'][0], build.kfont.load_bdf())
    assert out[0x2AC000:0x2AC000 + 64] == g


def test_script_syllables_outside_name_set_go_to_pages(src, msgs):
    ko = '뷁[FE69][F6]가[F6]가[F6]<FA>'
    _, cmap, _ = build.build(src, entry(msgs, 1571, ko), 'dev')
    assert cmap['뷁'][0] in (0xFD, 0xFC, 0xF4)


def test_fourth_page_f7_wired(src):
    out, _, _ = build.build(src, {}, 'dev')
    f = build.lorom_to_file
    # builder length table: F7 now 2 bytes
    assert out[0x7B5E + 0xF7] == 2
    # decoder dispatch for F7 points at a handler that writes hi byte 08
    tbl = f(0x9FBA20) + (0xF7 - 0xF2) * 2
    h = f(0x9F0000 | int.from_bytes(out[tbl:tbl + 2], 'little'))
    assert out[h:h + 2] == b'\xe2\x20' and b'\xa9\x08\x69\x00' in out[h:h + 42]
    # every kanji render mask widened to 12 bits
    for a in build.KANJI_MASK_SITES:
        assert out[f(a):f(a) + 3] == b'\x29\xff\x0f'


def test_page_f7_glyph_location(src, msgs):
    many = ''.join(chr(0xAC00 + i * 7) for i in range(1000))   # more than three pages
    lines = '<F8>\n'.join(many[i:i + 20] for i in range(0, 1000, 20))
    e = entry(msgs, 1571, lines + '[FE69][F6]가[F6]가[F6]<FA>')
    out, cmap, _ = build.build(src, e, 'dev')
    f7 = [c for c, v in cmap.items() if len(v) == 2 and v[0] == 0xF7]
    assert f7
    ch = f7[0]
    g = build.kfont.glyph_bytes(ch, build.kfont.load_bdf())
    o = build.NEW_KANJI + (3 * 256 + cmap[ch][1]) * 64
    assert out[o:o + 64] == g


def test_counter_glyph_slot_reserved(src, msgs):
    out, cmap, _ = build.build(src, {}, 'dev')
    assert b'\xfc\x93' not in cmap.values()
    o = build.NEW_KANJI + (1 * 256 + 0x93) * 64
    assert out[o:o + 64] == build.kfont.glyph_bytes('개', build.kfont.load_bdf())


def test_keep_source_exception(src, msgs):
    e = {2973: {'id': 2973, 'src': msgs[2973]['raw'], 'ko': '', 'keep_source': True,
                'state': 'distribution_eligible', 'note': 'grid bytes are glyph ids'}}
    sel, rep = build.select_texts(msgs, e, 'dev')
    assert sel[2973] == ('raw', bytes.fromhex(msgs[2973]['raw']))
    assert rep['kept_by_decision'] == [2973]
    e[2973]['state'] = 'needs_review'
    with pytest.raises(build.BuildError):
        build.select_texts(msgs, dict(e, **{i: {'id': i, 'src': msgs[i]['raw'], 'ko': '<FB>' if msgs[i]['raw'] == 'fb' else 'x', 'state': 'distribution_eligible'} for i in []}), 'release')


def test_title_logo_assets_patched(src):
    import lz2
    out, _, rep = build.build(src, {}, 'dev')
    def ptr(i):
        return out[0x11E3 + i] << 16 | out[0x12DC + i] << 8 | out[0x13D5 + i]
    def off(p):
        return ((p >> 16) - 0xC0) << 16 | (p & 0xFFFF)
    tiles = lz2.decompress(out, off(ptr(53)))
    mp = lz2.decompress(out, off(ptr(56)))
    assert len(tiles) == 8192 and len(mp) == 1024
    assert ptr(53) >> 16 >= 0xF0 and ptr(56) >> 16 >= 0xF0
    assert out[0x125B7C:0x125B98] != src[0x125B7C:0x125B98]
    assert rep['logo_tiles'] <= 256


def test_title_subtitle_asset_patched(src):
    import lz2
    out, _, _ = build.build(src, {}, 'dev')
    p = out[0x11E3 + 219] << 16 | out[0x12DC + 219] << 8 | out[0x13D5 + 219]
    assert p >> 16 >= 0xF0
    new = lz2.decompress(out, build.lz_offset(p))
    old = lz2.decompress(src, 0x1DA5ED)
    assert len(new) == len(old) and new != old


def test_intro_assets_patched(src):
    import lz2
    out, _, _ = build.build(src, {}, 'dev')
    for a in (57, 58, 59, 60):
        p = out[0x11E3 + a] << 16 | out[0x12DC + a] << 8 | out[0x13D5 + a]
        assert p >> 16 >= 0xF0
        assert len(lz2.decompress(out, build.lz_offset(p))) == 4096


def test_big_shout_pieces_replaced(src):
    import big_shout
    out, _, _ = build.build(src, {}, 'dev')
    b = big_shout.BASE
    assert out[b:b + big_shout.PIECES * 128] == big_shout.build()


def test_panel_labels_patched(src):
    import panel_gfx
    out, _, _ = build.build(src, {}, 'dev')
    for off, data in panel_gfx.build(src).items():
        assert out[off:off + 32] == data


def test_second_renderer_supports_half_space(src):
    out, _, _ = build.build(src, {}, 'dev')
    f = build.lorom_to_file
    # control 0x65 in the second dispatch table (9F:DEB6) -> half-space handler
    assert out[f(0x9FDEBC):f(0x9FDEBC) + 2] == (build.HALF_SPACE_HANDLER & 0xFFFF).to_bytes(2, 'little')
    # its blit 9F:E02E normalizes odd columns like 9F:BF97
    assert out[f(0x9FE02E):f(0x9FE02E) + 3] == b'\x20' + (build.BLIT_FIX & 0xFFFF).to_bytes(2, 'little')


def test_item_names_use_full_width_spaces(src, msgs):
    e = {3022: {'id': 3022, 'src': msgs[3022]['raw'], 'ko': '토 마토<FB>', 'state': 'in_progress'}}
    sel, _ = build.select_texts(msgs, e, 'dev')
    cmap = build.build_charmap([v for k, v in sel if k == 'ko'])
    parts, _ = build.encode_script(sel, cmap)
    assert koenc_half() not in parts[3022]
    assert 0xF0 in parts[3022]


def koenc_half():
    import koenc
    return koenc.HALF_SPACE


def test_drawn_blank_glyph_is_empty(src, msgs):
    ko = '가' + build.DRAWN_BLANK + '나<FB>'
    out, cmap, _ = build.build(src, {3022: {'id': 3022, 'src': msgs[3022]['raw'], 'ko': ko, 'state': 'in_progress'}}, 'dev')
    code = cmap[build.DRAWN_BLANK]
    assert len(code) == 2
    page = build.PAGE_ORDER.index('%02X' % code[0])
    o = build.NEW_KANJI + (page * 256 + code[1]) * 64
    assert out[o:o + 64] == bytes(64)


def test_poster_title_assets_patched(src):
    import lz2
    import poster_title
    out, _, _ = build.build(src, {}, 'dev')
    t = lz2.decompress(src, poster_title.TILES_OFFSET)
    m = lz2.decompress(src, poster_title.MAP_OFFSET)
    a = poster_title.TILES_ASSET
    p = out[0x11E3 + a] << 16 | out[0x12DC + a] << 8 | out[0x13D5 + a]
    assert p >> 16 >= 0xF0
    assert lz2.decompress(out, build.lz_offset(p)) == poster_title.build(t, m)
    a = poster_title.MAP_ASSET                      # shared with scenes 4F-55: never rewritten
    assert [out[tb + a] for tb in (0x11E3, 0x12DC, 0x13D5)] == [src[tb + a] for tb in (0x11E3, 0x12DC, 0x13D5)]


def test_scene_text_assets_patched(src):
    import lz2
    import scene_text
    out, _, _ = build.build(src, {}, 'dev')
    for a, data in scene_text.apply_all(src).items():
        p = out[0x11E3 + a] << 16 | out[0x12DC + a] << 8 | out[0x13D5 + a]
        assert p >> 16 >= 0xF0
        assert lz2.decompress(out, build.lz_offset(p)) == data


def test_riddle_patched(src):
    import lz2
    import riddle_text
    out, _, _ = build.build(src, {}, 'dev')
    import dud_sign
    tiles, writes = riddle_text.build(src)
    a = riddle_text.TILE_ASSET
    p = out[0x11E3 + a] << 16 | out[0x12DC + a] << 8 | out[0x13D5 + a]
    assert lz2.decompress(out, build.lz_offset(p)) == dud_sign.build(tiles)      # scene 0x50 shares asset 100
    for off, data in writes.items():
        assert out[off:off + len(data)] == data


def test_credits_patched(src):
    import lz2
    import credits_text
    out, _, _ = build.build(src, {}, 'dev')
    sheet = lz2.decompress(src, build.lz_offset(src[0x11E3 + 62] << 16 | src[0x12DC + 62] << 8 | src[0x13D5 + 62]))
    cmap = lz2.decompress(src, build.lz_offset(src[0x11E3 + 63] << 16 | src[0x12DC + 63] << 8 | src[0x13D5 + 63]))
    want = dict(zip((credits_text.SHEET_ASSET, credits_text.MAP_ASSET), credits_text.build(sheet, cmap)))
    for a, data in want.items():
        p = out[0x11E3 + a] << 16 | out[0x12DC + a] << 8 | out[0x13D5 + a]
        assert lz2.decompress(out, build.lz_offset(p)) == data


def test_default_output_name_carries_version():
    path = build.default_out()
    assert os.path.basename(path) == 'marvelous_ko_v%s.sfc' % build.VERSION
    assert os.path.dirname(path) == os.path.join(ROOT, 'build')


def test_readme_states_build_version():
    import re
    readme = open(os.path.join(ROOT, 'README.md'), encoding='utf-8').read()
    assert re.search(r'현재 버전: v(\d+\.\d+\.\d+(?:-[a-z]+)?)', readme).group(1) == build.VERSION


def test_lift_label_patched(src):
    import lz2
    import lift_label
    out, _, _ = build.build(src, {}, 'dev')
    a = lift_label.ASSET
    old = lz2.decompress(src, build.lz_offset(src[0x11E3 + a] << 16 | src[0x12DC + a] << 8 | src[0x13D5 + a]))
    p = out[0x11E3 + a] << 16 | out[0x12DC + a] << 8 | out[0x13D5 + a]
    assert lz2.decompress(out, build.lz_offset(p)) == lift_label.build(old)


def test_inline_icons_patched(src):
    import inline_icons
    out, _, _ = build.build(src, {}, 'dev')
    for off, data in inline_icons.build(src).items():
        assert out[off:off + 16] == data



def test_beta_policy_needs_full_translation_but_not_approval(msgs):
    full = {m['id']: {'id': m['id'], 'src': m['raw'], 'ko': '<FB>' if m['raw'] == 'fb' else 'x',
                      'state': 'needs_human_review'} for m in msgs[:3]}
    with pytest.raises(build.BuildError, match='no translation'):
        build.select_texts(msgs, {}, 'beta')                       # nothing translated
    i = msgs[0]['id']
    draft = {i: dict(full[i], state='in_progress')}
    with pytest.raises(build.BuildError, match='beta'):
        build.select_texts(msgs[:1], draft, 'beta')


def test_beta_build_of_real_translations(src):
    out, _, rep = build.build(src, build.load_translations(), 'beta')
    assert rep['policy'] == 'beta' and rep['public_beta'] and not rep['distribution']
    assert rep['source_kept'] == 0


def test_ips_round_trip(src):
    out, _, _ = build.build(src, {}, 'dev')
    patch = build.ips(src, out)
    assert patch[:5] == b'PATCH' and patch[-3:] == b'EOF'
    res = bytearray(src)
    p = 5
    while patch[p:p + 3] != b'EOF':
        off = int.from_bytes(patch[p:p + 3], 'big'); n = int.from_bytes(patch[p + 3:p + 5], 'big'); p += 5
        if n == 0:
            n = int.from_bytes(patch[p:p + 2], 'big'); res[off:off + n] = patch[p + 2:p + 3] * n; p += 3
        else:
            if len(res) < off + n:
                res.extend(b'\0' * (off + n - len(res)))
            res[off:off + n] = patch[p:p + n]; p += n
    assert bytes(res) == out
