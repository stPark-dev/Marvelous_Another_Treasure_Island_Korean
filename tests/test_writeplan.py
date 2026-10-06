import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))

import writeplan  # noqa: E402


def test_patch_checks_expected_source_bytes():
    src = bytes(16)
    wp = writeplan.WritePlan(src)
    wp.patch('ok', 2, b'\x01', expect=b'\x00')
    with pytest.raises(writeplan.PlanError):
        wp.patch('bad', 3, b'\x01', expect=b'\x07')


def test_overlapping_writes_rejected():
    wp = writeplan.WritePlan(bytes(16))
    wp.patch('a', 2, b'\x01\x02\x03')
    with pytest.raises(writeplan.PlanError):
        wp.patch('b', 4, b'\x09')


def test_expand_and_apply_reports_unplanned_diff():
    src = bytes(8)
    wp = writeplan.WritePlan(src, size=12, fill=0xFF)
    wp.patch('x', 9, b'\x05')
    out = wp.apply()
    assert len(out) == 12
    assert out[8] == 0xFF and out[9] == 0x05
    writeplan.verify(src, out, wp)          # planned writes + fill only
    bad = bytearray(out)
    bad[1] = 0x42
    with pytest.raises(writeplan.PlanError):
        writeplan.verify(src, bytes(bad), wp)


def test_protected_range_rejected():
    wp = writeplan.WritePlan(bytes(32))
    wp.protect('vectors', 16, 32)
    with pytest.raises(writeplan.PlanError):
        wp.patch('oops', 20, b'\x00')
