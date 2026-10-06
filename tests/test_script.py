import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))

import mvscript  # noqa: E402

ROM_PATH = os.path.join(ROOT, 'rom', 'baserom.sfc')
needs_rom = pytest.mark.skipif(not os.path.exists(ROM_PATH), reason='source ROM not present')


@pytest.fixture(scope='module')
def rom():
    with open(ROM_PATH, 'rb') as f:
        return f.read()


@needs_rom
def test_builder_finds_3077_starts_and_ff_end(rom):
    starts, end = mvscript.builder_boundaries(rom)
    assert len(starts) == 3077
    assert end == 0x23BF9D
    assert rom[end] == 0xFF


@needs_rom
def test_extract_round_trips_script_block(rom):
    msgs, end = mvscript.extract(rom)
    assert len(msgs) == 3076
    blob = b''.join(bytes.fromhex(m['raw']) for m in msgs)
    assert blob == rom[mvscript.SCRIPT_START:end]


@needs_rom
def test_known_message_decodes(rom):
    msgs, _ = mvscript.extract(rom)
    m = msgs[1571]
    assert m['offset'] == 0x22D712
    assert m['jp'].startswith('われわれ、この島に住むサルは、代々この島の<F8>\n秘密')


def test_tokenize_lengths():
    data = bytes([0x01, 0xFD, 0x74, 0xF4, 0x3B, 0xF5, 0x02, 0x1A, 0xFE, 0x66, 0x01, 0x02,
                  0xFE, 0x6D, 0x08, 0xFE, 0x69, 0xF8, 0xFA])
    toks, nxt = mvscript.tokenize(data, 0)
    assert nxt == len(data)
    assert [len(raw) for _, raw in toks] == [1, 2, 2, 3, 4, 3, 2, 1, 1]


def test_tokenize_big_font_runs_to_end():
    data = bytes([0xFE, 0x7C, 0x0A, 0xF8, 0x0C, 0xF9, 0x0F, 0xFA])
    toks, nxt = mvscript.tokenize(data, 0)
    assert nxt == len(data)
    assert [k for k, _ in toks] == ['ctrl', 'big', 'ctrl', 'big', 'ctrl', 'big', 'end']
