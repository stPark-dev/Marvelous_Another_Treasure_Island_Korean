"""Collect items needing human judgment into docs/review_questions.md."""
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mvscript  # noqa: E402

ROOT = mvscript.ROOT


def one(s):
    return s.replace('\n', ' ').replace('<F8>', '/')


def main():
    q, sug = [], []
    for fn in sorted(glob.glob(os.path.join(ROOT, 'text', 'ko', '*.json'))):
        for e in json.load(open(fn, encoding='utf-8'))['entries']:
            for r in e.get('review', []):
                if r['kind'] == 'question':
                    q.append((e['id'], e, r))
                elif r['kind'] == 'suggestion' and r.get('proposed'):
                    sug.append((e['id'], e, r))
    out = ['# 사람 판단이 필요한 항목', '',
           '검수(독립 2차)에서 나온 질문과, 자동 적용하지 않은 문장 제안. 각 항목은 현재 문장(`ko`)과 함께 적는다.', '',
           '## 1. 질문 (%d건)' % len(q), '']
    for i, e, r in q:
        out.append('- **%04d** %s  \n  원문: %s  \n  현재: %s' % (i, one(r['reason']), one(e['jp'])[:80], one(e['ko'])[:80]))
    out += ['', '## 2. 문장 제안 (%d건, 미적용)' % len(sug), '']
    for i, e, r in sug:
        out.append('- **%04d** %s  \n  현재: %s  \n  제안: %s' % (i, one(r['reason']), one(e['ko'])[:80], one(r['proposed'])[:80]))
    with open(os.path.join(ROOT, 'docs', 'review_questions.md'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(out) + '\n')
    print('questions %d, suggestions %d' % (len(q), len(sug)))


if __name__ == '__main__':
    main()
