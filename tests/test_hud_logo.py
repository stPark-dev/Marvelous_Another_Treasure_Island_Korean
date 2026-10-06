import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))

import hud_logo  # noqa: E402


def test_logo_size_and_colours():
    d = hud_logo.build()
    assert len(d) == 0x200
    assert any(d)
