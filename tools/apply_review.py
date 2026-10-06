"""Apply an independent review to a translation batch.

  python tools/apply_review.py b01        reads work/review/b01.json

Review file: {"batch": "b01", "items": [{"id": 4, "kind": "error|consistency|
suggestion|question", "proposed": "<full ko text or empty>", "reason": "..."}]}

error/consistency items with a proposed text replace the draft (the replaced
draft is kept in "draft_ko"); every item is appended to the entry's "review"
list; reviewed entries move to needs_human_review.  Each proposed text must
pass the same mechanical checks as a draft.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import check_ko   # noqa: E402
import kfont      # noqa: E402
import mvscript   # noqa: E402

ROOT = mvscript.ROOT
APPLY_KINDS = {'error', 'consistency'}


def apply(doc, review, msgs, bdf):
    byid = {e['id']: e for e in doc['entries']}
    problems = []
    for it in review['items']:
        e = byid.get(it['id'])
        if e is None:
            problems.append((it['id'], 'not in batch'))
            continue
        e.setdefault('review', []).append({k: it.get(k, '') for k in ('kind', 'proposed', 'reason')})
        if it['kind'] in APPLY_KINDS and it.get('proposed'):
            cand = dict(e, ko=it['proposed'])
            p = check_ko.check_entry(cand, msgs[e['id']], bdf)
            if p:
                problems += [(e['id'], 'proposed: ' + x) for x in p]
                continue
            e.setdefault('draft_ko', e['ko'])
            e['ko'] = it['proposed']
    for e in doc['entries']:
        if e.get('ko') and e.get('state') == 'needs_review':
            e['state'] = 'needs_human_review'
    return problems


def main():
    name = sys.argv[1]
    kp = os.path.join(ROOT, 'text', 'ko', name + '.json')
    with open(kp, encoding='utf-8') as f:
        doc = json.load(f)
    with open(os.path.join(ROOT, 'work', 'review', name + '.json'), encoding='utf-8') as f:
        review = json.load(f)
    with open(os.path.join(ROOT, 'rom', 'baserom.sfc'), 'rb') as f:
        msgs, _ = mvscript.extract(f.read())
    probs = apply(doc, review, msgs, kfont.load_bdf())
    for i, p in probs:
        print('#%04d %s' % (i, p))
    if probs:
        sys.exit('%s: %d problem(s); nothing written' % (name, len(probs)))
    with open(kp, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    print('%s: applied %d review items' % (name, len(review['items'])))


if __name__ == '__main__':
    main()
