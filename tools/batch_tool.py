"""Translation batch helper.

  python tools/batch_tool.py init  b01 0 288     write work/tr/b01.txt (source view, empty slots)
  python tools/batch_tool.py merge b01           text/ko/b01.json from work/tr/b01.txt

Text format, one block per message:

  ### 0004
  #jp ・・・・あれっ？<F8>…           (source, ignored on merge)
  ……어라?<F8>
  선생님 목소리가……<FA>
  #note 해석 메모 (optional)
  #q 사람이 정할 질문 (optional)

Protected fields (id, src, jp) always come from the ROM extraction, never from
the text file.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import build      # noqa: E402
import mvscript   # noqa: E402

ROOT = mvscript.ROOT
TR_DIR = os.path.join(ROOT, 'work', 'tr')
KO_DIR = os.path.join(ROOT, 'text', 'ko')


def load_msgs():
    with open(os.path.join(ROOT, 'rom', 'baserom.sfc'), 'rb') as f:
        return mvscript.extract(f.read())[0]


def init_text(msgs, start, end):
    out = []
    for m in msgs[start:end + 1]:
        out.append('### %04d' % m['id'])
        out.append('#jp ' + m['jp'].replace('\n', ''))
        out.append('')
    return '\n'.join(out)


def parse_text(text):
    blocks = {}
    for part in re.split(r'^### ', text, flags=re.M)[1:]:
        head, _, body = part.partition('\n')
        i = int(head.strip())
        if i in blocks:
            raise ValueError('duplicate block %04d' % i)
        ko, note, q = [], [], []
        for line in body.split('\n'):
            if line.startswith('#jp'):
                continue
            if line.startswith('#note'):
                note.append(line[5:].strip())
            elif line.startswith('#q'):
                q.append(line[2:].strip())
            else:
                ko.append(line)
        blocks[i] = {'ko': '\n'.join(ko).strip('\n'), 'note': ' '.join(note), 'question': ' '.join(q)}
    return blocks


def merge(msgs, name, blocks):
    entries = []
    for i in sorted(blocks):
        b = blocks[i]
        m = msgs[i]
        entries.append({'id': i, 'src': m['raw'], 'jp': m['jp'], 'ko': b['ko'],
                        'state': 'needs_review' if b['ko'] else 'untranslated',
                        'note': b['note'], 'question': b['question']})
    return {'batch': name, 'source_sha256': build.SOURCE_SHA256, 'entries': entries}


def main():
    cmd, name = sys.argv[1], sys.argv[2]
    msgs = load_msgs()
    os.makedirs(TR_DIR, exist_ok=True)
    tpath = os.path.join(TR_DIR, name + '.txt')
    if cmd == 'init':
        if os.path.exists(tpath):
            sys.exit('%s exists; refusing to overwrite' % tpath)
        with open(tpath, 'w', encoding='utf-8') as f:
            f.write(init_text(msgs, int(sys.argv[3]), int(sys.argv[4])))
        print(tpath)
    elif cmd == 'merge':
        with open(tpath, encoding='utf-8') as f:
            doc = merge(msgs, name, parse_text(f.read()))
        with open(os.path.join(KO_DIR, name + '.json'), 'w', encoding='utf-8') as f:
            json.dump(doc, f, ensure_ascii=False, indent=1)
        n = sum(1 for e in doc['entries'] if e['ko'])
        print('%s: %d/%d translated' % (name, n, len(doc['entries'])))
    else:
        sys.exit(__doc__)


if __name__ == '__main__':
    main()
