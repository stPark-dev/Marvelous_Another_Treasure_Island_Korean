"""Mechanical checks for Korean translation batch files.

  python tools/check_ko.py text/ko/b01.json [...]

Checks per entry: source baseline matches the ROM extraction, the text parses,
ends with the source terminator, keeps the protected control sequence (only
<F8> line breaks and [F9] page waits may move), every line fits 22 cells and
every character has a glyph (fixed table or Galmuri).  Prints one line per
problem and exits non-zero when any is found.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import build      # noqa: E402
import kfont      # noqa: E402
import koenc      # noqa: E402
import mvscript   # noqa: E402

ALLOWED_STATES = {'untranslated', 'in_progress', 'needs_review', 'needs_human_review', 'distribution_eligible'}
FORBIDDEN_CHARS = set('ぁ-んァ-ヶ')


def check_entry(e, msg, bdf):
    probs = []
    if e.get('src') != msg['raw']:
        probs.append('source baseline differs from ROM extraction')
    if e.get('state') not in ALLOWED_STATES:
        probs.append('unknown state %r' % e.get('state'))
    ko = e.get('ko')
    if not ko:
        return probs
    try:
        toks = koenc.parse(ko)
    except koenc.EncodeError as ex:
        return probs + ['parse: %s' % ex]
    src_end = bytes.fromhex(msg['raw'])[-1:]
    if not toks or toks[-1] != ('raw', src_end):
        probs.append('must end with <%s>' % src_end.hex().upper())
    if build.protected_sequence(bytes.fromhex(msg['raw'])) != build.protected_sequence(ko):
        want = ' '.join(t.hex().upper() for t in build.protected_sequence(bytes.fromhex(msg['raw'])))
        got = ' '.join(t.hex().upper() for t in build.protected_sequence(ko))
        probs.append('control sequence changed: want [%s] got [%s]' % (want, got))
    probs += build.layout_problems(e['id'], msg['raw'], ko)
    for kind, v in toks:
        if kind != 'char' or v in build.FIXED:
            continue
        if ('ぁ' <= v <= 'ヿ') or ('一' <= v <= '鿿'):
            probs.append('Japanese character %r left in translation' % v)
        elif ord(v) not in bdf:
            probs.append('no glyph for %r (U+%04X)' % (v, ord(v)))
    return probs


def check_file(path, msgs, bdf):
    with open(path, encoding='utf-8') as f:
        doc = json.load(f)
    out = []
    seen = set()
    for e in doc['entries']:
        i = e['id']
        if i in seen:
            out.append((i, 'duplicate id'))
        seen.add(i)
        if not 0 <= i < len(msgs):
            out.append((i, 'id out of range'))
            continue
        out += [(i, p) for p in check_entry(e, msgs[i], bdf)]
    return out


def main():
    with open(os.path.join(mvscript.ROOT, 'rom', 'baserom.sfc'), 'rb') as f:
        msgs, _ = mvscript.extract(f.read())
    bdf = kfont.load_bdf()
    bad = 0
    for path in sys.argv[1:]:
        probs = check_file(path, msgs, bdf)
        for i, p in probs:
            print('%s #%04d: %s' % (os.path.basename(path), i, p))
        bad += len(probs)
        print('%s: %s' % (os.path.basename(path), 'OK' if not probs else '%d problem(s)' % len(probs)))
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
