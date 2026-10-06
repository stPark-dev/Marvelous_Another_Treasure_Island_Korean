import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))

import koenc  # noqa: E402


def test_parse_tokens_and_newline_marker():
    toks = koenc.parse('가 나　<F8>\n다[FE6D08][F9]라<FA>')
    assert toks == [('char', '가'), ('half', None), ('char', '나'), ('full', None),
                    ('raw', b'\xf8'), ('char', '다'), ('raw', b'\xfe\x6d\x08'),
                    ('raw', b'\xf9'), ('char', '라'), ('raw', b'\xfa')]


def test_parse_rejects_bare_newline():
    with pytest.raises(koenc.EncodeError):
        koenc.parse('가\n나<FA>')


def test_parse_rejects_bad_raw_token():
    with pytest.raises(koenc.EncodeError):
        koenc.parse('가[F]<FA>')


def test_allocate_frequency_order_one_byte_then_pages():
    cmap = koenc.allocate({'가': 5, '나': 9, '다': 1}, one_byte=[0x10, 0x11], pages=['FD'])
    assert cmap['나'] == b'\x10'
    assert cmap['가'] == b'\x11'
    assert cmap['다'] == b'\xfd\x00'


def test_allocate_tie_breaks_by_codepoint():
    cmap = koenc.allocate({'다': 3, '가': 3}, one_byte=[0x00, 0x01], pages=[])
    assert cmap['가'] == b'\x00' and cmap['다'] == b'\x01'


def test_allocate_overflow_raises():
    with pytest.raises(koenc.EncodeError):
        koenc.allocate({'가': 1, '나': 1}, one_byte=[0x00], pages=[])


def test_allocate_skips_fixed_chars():
    cmap = koenc.allocate({'가': 1, '!': 50}, one_byte=[0x00], pages=[], fixed={'!': b'\xdf'})
    assert cmap == {'!': b'\xdf', '가': b'\x00'}


def test_encode_maps_spaces_and_raw():
    cmap = {'가': b'\x00', '나': b'\xfd\x01'}
    out = koenc.encode('가 나　<F8>\n[F9]<FA>', cmap)
    assert out == bytes([0x00, koenc.HALF_SPACE, 0xFD, 0x01, koenc.FULL_SPACE, 0xF8, 0xF9, 0xFA])


def test_encode_unmapped_char_fails():
    with pytest.raises(koenc.UnmappedChar):
        koenc.encode('가힣<FA>', {'가': b'\x00'})


def test_encode_requires_single_terminator_at_end():
    cmap = {'가': b'\x00'}
    with pytest.raises(koenc.EncodeError):
        koenc.encode('가', cmap)
    with pytest.raises(koenc.EncodeError):
        koenc.encode('가<FA>가<FA>', cmap)


def test_count_chars_ignores_tokens_and_spaces():
    c = koenc.count_chars(['가 가[F9]<F8>\n나<FA>', '나<FB>'])
    assert c == {'가': 2, '나': 2}


def test_line_widths_in_half_cells():
    # full glyph = 2 half cells, half space = 1, full space = 2
    assert koenc.line_widths('가 나<F8>\n다다다[F9]라<FA>') == [5, 6, 2]


def test_line_widths_count_insertions():
    # icon = 1 cell, team name = 5 cells, leader name = 4 cells, number = 3 cells
    assert koenc.line_widths('[FE6D0A]버튼<FA>') == [2 + 4]
    assert koenc.line_widths('[FE6D1A] 팀<FA>') == [10 + 1 + 2]
    assert koenc.line_widths('[FE6D34] 군<FA>') == [8 + 1 + 2]
    assert koenc.line_widths('[FE6B]개<FA>') == [6 + 2]
    assert koenc.line_widths('[F5021A]가<FA>') == [2]


def test_insertions_are_aligned_to_even_columns():
    cmap = {'가': b'\x00'}
    # one half space before the icon -> odd column -> encoder pads with another half space
    out = koenc.encode('가 [FE6D0A]가<FA>', cmap)
    assert out == bytes([0x00, koenc.HALF_SPACE, koenc.HALF_SPACE, 0xFE, 0x6D, 0x0A, 0x00, 0xFA])
    # already even: no padding
    out = koenc.encode('가  [FE6B]<FA>', cmap)
    assert out == bytes([0x00, koenc.HALF_SPACE, koenc.HALF_SPACE, 0xFE, 0x6B, 0xFA])
    # parity resets at line breaks
    out = koenc.encode('가 <F8>\n[FE6C]<FA>', cmap)
    assert out == bytes([0x00, koenc.HALF_SPACE, 0xF8, 0xFE, 0x6C, 0xFA])


def test_line_widths_include_alignment_padding():
    assert koenc.line_widths('가 [FE6D0A]<FA>') == [2 + 1 + 1 + 2]
