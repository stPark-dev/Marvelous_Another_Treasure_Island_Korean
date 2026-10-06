import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))

import lz2  # noqa: E402


def test_decompress_each_command():
    data = bytes([0x02, 1, 2, 3,          # direct copy 3
                  0x22, 9,                # byte fill 3
                  0x41, 7, 8,             # word fill 2
                  0x62, 5,                # increasing fill 3
                  0x81, 0x00, 0x01,       # copy 2 from offset 1 (big-endian)
                  0xFF])
    assert lz2.decompress(data) == bytes([1, 2, 3, 9, 9, 9, 7, 8, 5, 6, 7, 2, 3])


def test_extended_length():
    data = bytes([0xE4, 0x09, 0x55, 0xFF])   # cmd 1, length 0x00A
    assert lz2.decompress(data) == bytes([0x55]) * 10


def test_roundtrip_random_and_structured():
    rnd = random.Random(1)
    samples = [bytes(rnd.randrange(256) for _ in range(3000)),
               bytes([0]) * 5000,
               bytes(range(256)) * 9,
               bytes([1, 2]) * 700 + bytes(rnd.randrange(4) for _ in range(2000))]
    for s in samples:
        c = lz2.compress(s)
        assert lz2.decompress(c) == s
        assert c[-1] == 0xFF


def test_compression_is_effective_on_repetitive_data():
    s = bytes([0]) * 4096
    assert len(lz2.compress(s)) < 64


def test_long_length_form():
    # 110 ccc xx + 16-bit big-endian length-1 : cmd 1 (fill), length 0x0103
    data = bytes([0xC4, 0x01, 0x02, 0x77, 0xFF])
    assert lz2.decompress(data) == bytes([0x77]) * 0x103
