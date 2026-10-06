import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))

import check_ko   # noqa: E402
import kfont      # noqa: E402
import mvscript   # noqa: E402

ROM_PATH = os.path.join(ROOT, 'rom', 'baserom.sfc')
pytestmark = pytest.mark.skipif(not os.path.exists(ROM_PATH), reason='source ROM not present')


@pytest.fixture(scope='module')
def ctx():
    with open(ROM_PATH, 'rb') as f:
        msgs, _ = mvscript.extract(f.read())
    return msgs, kfont.load_bdf()


def probs(ctx, i, ko, **kw):
    msgs, bdf = ctx
    e = {'id': i, 'src': msgs[i]['raw'], 'ko': ko, 'state': 'in_progress'}
    e.update(kw)
    return check_ko.check_entry(e, msgs[i], bdf)


def test_good_entry(ctx):
    assert probs(ctx, 1572, '[F2]윙키는 장로님에게서 「세 개의 열쇠」를<F8>\n받았다.<FA>') == []


def test_wrong_terminator(ctx):
    assert any('must end' in p for p in probs(ctx, 1572, '[F2]윙키<FB>'))


def test_leftover_japanese(ctx):
    assert any('Japanese' in p for p in probs(ctx, 1572, '[F2]윙키は<FA>'))


def test_dropped_control(ctx):
    assert any('control sequence' in p for p in probs(ctx, 1572, '윙키<FA>'))


def test_long_line(ctx):
    assert any('cells' in p for p in probs(ctx, 1572, '[F2]' + '가' * 23 + '<FA>'))


def test_bad_state_and_baseline(ctx):
    p = probs(ctx, 1572, '[F2]윙키<FA>', state='done', src='fa')
    assert any('state' in x for x in p) and any('baseline' in x for x in p)


def test_pool_policy_requires_same_glyph_count(ctx):
    msgs, bdf = ctx
    jp = msgs[2976]['jp']
    n = len(jp.replace('<FB>', ''))
    ok = '가' * n + '<FB>'
    assert check_ko.check_entry({'id': 2976, 'src': msgs[2976]['raw'], 'ko': ok, 'state': 'in_progress'}, msgs[2976], bdf) == []
    short = '가' * (n - 1) + '<FB>'
    assert any('pool' in p for p in check_ko.check_entry({'id': 2976, 'src': msgs[2976]['raw'], 'ko': short, 'state': 'in_progress'}, msgs[2976], bdf))
    half = '가 ' + '가' * (n - 2) + '<FB>'
    assert any('pool' in p for p in check_ko.check_entry({'id': 2976, 'src': msgs[2976]['raw'], 'ko': half, 'state': 'in_progress'}, msgs[2976], bdf))


def test_item_policy_width(ctx):
    msgs, bdf = ctx
    e = {'id': 3022, 'src': msgs[3022]['raw'], 'ko': '가' * 15 + '<FB>', 'state': 'in_progress'}
    assert any('cells' in p for p in check_ko.check_entry(e, msgs[3022], bdf))
