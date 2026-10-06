import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))

import batch_tool  # noqa: E402

MSGS = [{'id': 0, 'raw': 'fb', 'jp': '<FB>'},
        {'id': 1, 'raw': 'f8fb', 'jp': '<F8>\nあ<FB>'}]


def test_init_then_parse_roundtrip_empty():
    t = batch_tool.init_text(MSGS, 0, 1)
    b = batch_tool.parse_text(t)
    assert b == {0: {'ko': '', 'note': '', 'question': ''}, 1: {'ko': '', 'note': '', 'question': ''}}


def test_parse_multiline_note_question():
    t = '### 0001\n#jp x\n<F8>\n가<FB>\n#note 메모\n#q 질문\n\n### 0000\n<FB>\n'
    b = batch_tool.parse_text(t)
    assert b[1] == {'ko': '<F8>\n가<FB>', 'note': '메모', 'question': '질문'}
    assert b[0]['ko'] == '<FB>'


def test_merge_takes_protected_fields_from_extraction():
    doc = batch_tool.merge(MSGS, 'bx', {1: {'ko': '<F8>\n가<FB>', 'note': '', 'question': ''}})
    e = doc['entries'][0]
    assert (e['id'], e['src'], e['jp'], e['state']) == (1, 'f8fb', '<F8>\nあ<FB>', 'needs_review')


def test_duplicate_block_rejected():
    import pytest
    with pytest.raises(ValueError):
        batch_tool.parse_text('### 0001\n가\n### 0001\n나\n')
