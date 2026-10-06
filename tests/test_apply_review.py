import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))

import apply_review  # noqa: E402
import kfont         # noqa: E402
import mvscript      # noqa: E402

ROM_PATH = os.path.join(ROOT, 'rom', 'baserom.sfc')
pytestmark = pytest.mark.skipif(not os.path.exists(ROM_PATH), reason='source ROM not present')


@pytest.fixture(scope='module')
def ctx():
    with open(ROM_PATH, 'rb') as f:
        return mvscript.extract(f.read())[0], kfont.load_bdf()


def doc(msgs):
    return {'entries': [{'id': 1572, 'src': msgs[1572]['raw'], 'ko': '[F2]윙키<FA>', 'state': 'needs_review'},
                        {'id': 3, 'src': msgs[3]['raw'], 'ko': '실패<FB>', 'state': 'needs_review'}]}


def test_error_replaces_and_keeps_draft(ctx):
    msgs, bdf = ctx
    d = doc(msgs)
    rv = {'items': [{'id': 1572, 'kind': 'error', 'proposed': '[F2]윙키는 열쇠를 받았다.<FA>', 'reason': '누락'},
                    {'id': 3, 'kind': 'suggestion', 'proposed': '실패 메시지<FB>', 'reason': '취향'}]}
    assert apply_review.apply(d, rv, msgs, bdf) == []
    e0, e1 = d['entries']
    assert e0['ko'] == '[F2]윙키는 열쇠를 받았다.<FA>' and e0['draft_ko'] == '[F2]윙키<FA>'
    assert e1['ko'] == '실패<FB>' and e1['review'][0]['kind'] == 'suggestion'
    assert e0['state'] == e1['state'] == 'needs_human_review'


def test_bad_proposal_rejected(ctx):
    msgs, bdf = ctx
    d = doc(msgs)
    rv = {'items': [{'id': 1572, 'kind': 'error', 'proposed': '윙키<FA>', 'reason': 'x'}]}
    assert apply_review.apply(d, rv, msgs, bdf)
    assert d['entries'][0]['ko'] == '[F2]윙키<FA>'
