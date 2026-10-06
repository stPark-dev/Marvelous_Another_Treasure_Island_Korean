"""Marvelous (SFC) dialogue script codec.

The script is one contiguous block starting at E1:B400 (file 0x21B400) and
ending with an FF byte.  At boot the SA-1 routine 00:FC7B scans it with the
length tables at 00:FB5E / 00:FBFB and stores one 24-bit pointer per message
(the start, and every byte after FA/FB) at BW-RAM 40:DBE0.  The S-CPU decoder
9F:BA3A expands a message into renderer codes at 40:A400.

Token grammar (decoder 9F:BA57 semantics):
  00-F1        kana page glyph (one byte)
  FD xx        kanji page 0     FC xx  kanji page 1     F4 xx  kanji page 2
  F2 F3 F6 F7 F8 F9            one-byte controls
  F5 a b       insert (same handler as FE 66)
  FA / FB      end of message
  FE 66 a b    FE 6D a       FE 7C ... (big font until FA/FB)   FE xx (other)
"""
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT_START = 0x21B400
BUILDER_LEN = 0x7B5E      # 00:FB5E, indexed by max(byte, F2)
BUILDER_FE_LEN = 0x7BFB   # 00:FBFB, indexed by the FE argument

CTRL1 = {0xF2, 0xF3, 0xF6, 0xF7, 0xF8, 0xF9}
KANJI_PREFIX = {0xFD: 'FD', 0xFC: 'FC', 0xF4: 'F4'}


def load_table(path=None):
    path = path or os.path.join(ROOT, 'data', 'jp_table.txt')
    pages, cur = {}, None
    for line in open(path, encoding='utf-8').read().split('\n'):
        if not line or line.startswith('#'):
            continue
        if line.startswith('['):
            cur = line[1:-1]
            pages[cur] = ''
            continue
        pages[cur] += line
    return pages


def builder_boundaries(rom):
    """Message start offsets exactly as the SA-1 builder 00:FC7B computes them.

    Returns (starts, end) where end is the offset of the terminating FF.
    """
    L = rom[BUILDER_LEN:BUILDER_LEN + 0x100]
    A = rom[BUILDER_FE_LEN:BUILDER_FE_LEN + 0x100]
    p = SCRIPT_START
    starts = [p]
    while True:
        b = rom[p]
        if b == 0xFF:
            return starts, p
        arg = rom[p + 1]
        p += L[max(b, 0xF2)]
        if b in (0xFA, 0xFB):
            starts.append(p)
        elif b == 0xFE:
            p += A[arg]


def tokenize(data, pos):
    """Split one message at data[pos:] into (kind, bytes) tokens up to FA/FB."""
    toks = []
    big = False
    while True:
        b = data[pos]
        if b in (0xFA, 0xFB):
            toks.append(('end', data[pos:pos + 1]))
            return toks, pos + 1
        if big:
            if b in (0xF8, 0xF9):
                toks.append(('ctrl', data[pos:pos + 1]))
            else:
                toks.append(('big', data[pos:pos + 1]))
            pos += 1
            continue
        if b < 0xF2:
            toks.append(('kana', data[pos:pos + 1]))
            n = 1
        elif b in KANJI_PREFIX:
            toks.append(('kanji', data[pos:pos + 2]))
            n = 2
        elif b in CTRL1:
            toks.append(('ctrl', data[pos:pos + 1]))
            n = 1
        elif b == 0xF5:
            toks.append(('ctrl', data[pos:pos + 3]))
            n = 3
        elif b == 0xFE:
            sub = data[pos + 1]
            n = {0x66: 4, 0x6D: 3}.get(sub, 2)
            toks.append(('ctrl', data[pos:pos + n]))
            if sub == 0x7C:
                big = True
        else:
            raise ValueError('unexpected byte %02X at %X' % (b, pos))
        pos += n


def render(toks, tbl):
    out = []
    for kind, raw in toks:
        if kind == 'kana' and raw[0] < len(tbl['kana']):
            out.append(tbl['kana'][raw[0]])
        elif kind == 'kanji':
            page = tbl[KANJI_PREFIX[raw[0]]]
            out.append(page[raw[1]] if raw[1] < len(page) else '[%s]' % raw.hex().upper())
        elif kind == 'end':
            out.append('<%02X>' % raw[0])
        elif kind == 'ctrl' and raw == b'\xf8':
            out.append('<F8>\n')
        else:
            out.append('[%s]' % raw.hex().upper())
    return ''.join(out)


def extract(rom, tbl=None):
    tbl = tbl or load_table()
    starts, end = builder_boundaries(rom)
    msgs = []
    for i, s in enumerate(starts):
        if s == end:
            break
        toks, nxt = tokenize(rom, s)
        if i + 1 < len(starts) and nxt != starts[i + 1]:
            raise ValueError('message %d: decoder end %X != builder start %X' % (i, nxt, starts[i + 1]))
        msgs.append({'id': i, 'offset': s, 'raw': rom[s:nxt].hex(), 'jp': render(toks, tbl)})
    return msgs, end


if __name__ == '__main__':
    import json
    import sys
    rom = open(sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'rom', 'baserom.sfc'), 'rb').read()
    msgs, end = extract(rom)
    out = os.path.join(ROOT, 'text', 'script_jp.json')
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(msgs, f, ensure_ascii=False, indent=1)
    print('%d messages, script %X..%X (%d bytes) -> %s' % (len(msgs), SCRIPT_START, end, end - SCRIPT_START, out))
