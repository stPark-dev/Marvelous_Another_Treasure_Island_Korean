"""Korean script encoder for the Marvelous dialogue format.

Text syntax (shared with the extracted Japanese rendering):
  <XX>        one raw control byte; "<F8>" may be followed by a cosmetic newline
  [HEX..]     raw bytes (controls with arguments), e.g. [FE6D08]
  ' '         half-width space (8 px)      '　' full-width space (16 px)
  any other   a glyph looked up in the character map
"""
import re
from collections import Counter

FULL_SPACE = 0xF0
HALF_SPACE = 0xF3      # unused in the original script; patched to an 8 px advance
LINE_END_BYTES = {0xF6, 0xF8, 0xF9, 0xFA, 0xFB}
END_BYTES = {0xFA, 0xFB}
PAGE_PREFIX = {'FD': 0xFD, 'FC': 0xFC, 'F4': 0xF4, 'F7': 0xF7}

_TOKEN = re.compile(r'<([0-9A-F]{2})>(\n)?|\[([0-9A-F]+)\]|(\n)|(.)', re.S)


class EncodeError(ValueError):
    pass


class UnmappedChar(EncodeError):
    pass


def parse(text):
    toks = []
    for m in _TOKEN.finditer(text):
        ctrl, _nl, raw, bare_nl, ch = m.groups()
        if ctrl is not None:
            toks.append(('raw', bytes.fromhex(ctrl)))
        elif raw is not None:
            if len(raw) % 2:
                raise EncodeError('odd raw token [%s]' % raw)
            toks.append(('raw', bytes.fromhex(raw)))
        elif bare_nl is not None:
            raise EncodeError('newline must follow <F8>: %r' % text)
        elif ch in '[]<>':
            raise EncodeError('malformed token near %r in %r' % (ch, text))
        elif ch == ' ':
            toks.append(('half', None))
        elif ch == '　':
            toks.append(('full', None))
        else:
            toks.append(('char', ch))
    return toks


def count_chars(texts):
    c = Counter()
    for t in texts:
        for kind, v in parse(t):
            if kind == 'char':
                c[v] += 1
    return dict(c)


def allocate(freq, one_byte, pages, fixed=None, reserved=()):
    """Assign codes: most frequent characters to one-byte slots, the rest to pages."""
    cmap = dict(fixed or {})
    slots = [bytes([b]) for b in one_byte]
    for p in pages:
        slots += [bytes([PAGE_PREFIX[p], i]) for i in range(256)]
    slots = [s for s in slots if s not in set(reserved)]
    todo = sorted((ch for ch in freq if ch not in cmap), key=lambda ch: (-freq[ch], ord(ch)))
    if len(todo) > len(slots):
        raise EncodeError('%d characters exceed %d glyph slots' % (len(todo), len(slots)))
    for ch, code in zip(todo, slots):
        cmap[ch] = code
    return cmap


def is_insertion(raw):
    return (raw[:2] == b'\xfe\x6d' and len(raw) == 3) or raw in (b'\xfe\x6b', b'\xfe\x6c')


def is_line_end(raw):
    return raw[0] in LINE_END_BYTES or raw[:2] == b'\xfe\x69'


def layout(toks):
    """Insert a half space before any insertion that would start on an odd
    8 px column: the icon/number/name handlers assume an even $9C."""
    out, odd = [], False
    for kind, v in toks:
        if kind == 'half':
            odd = not odd
        elif kind == 'raw':
            if is_line_end(v):
                odd = False
            elif is_insertion(v) and odd:
                out.append(('half', None))
                odd = False
        out.append((kind, v))
    return out


def encode(text, cmap):
    out = bytearray()
    toks = layout(parse(text))
    for i, (kind, v) in enumerate(toks):
        if kind == 'char':
            if v not in cmap:
                raise UnmappedChar('unmapped character %r (U+%04X)' % (v, ord(v)))
            out += cmap[v]
        elif kind == 'half':
            out.append(HALF_SPACE)
        elif kind == 'full':
            out.append(FULL_SPACE)
        else:
            if v[0] in END_BYTES and i != len(toks) - 1:
                raise EncodeError('terminator before end: %r' % text)
            out += v
    if not toks or toks[-1][0] != 'raw' or toks[-1][1][0] not in END_BYTES:
        raise EncodeError('message must end with <FA> or <FB>: %r' % text)
    return bytes(out)


# Rendered width (half cells) of inline insertions, from the 9F:C5CE dispatcher:
# default FE6D arguments draw one 16 px icon; 1A is the team name (5 cells,
# trailing blanks trimmed), 34/56 a 4-cell leader name.  Other special FE6D
# arguments and the FE6B/FE6C numbers are budgeted at 3 cells.
FE6D_WIDTH = {0x1A: 10, 0x34: 8, 0x56: 8, 0x12: 6, 0x18: 6, 0x1C: 6, 0x38: 6, 0x42: 6}
NUMBER_WIDTH = 6


def insertion_width(raw):
    if raw[:2] == b'\xfe\x6d' and len(raw) == 3:
        return FE6D_WIDTH.get(raw[2], 2)
    if raw in (b'\xfe\x6b', b'\xfe\x6c'):
        return NUMBER_WIDTH
    return 0


def line_widths(text):
    """Visible width of each line in 8 px half cells (glyph=2, half space=1, full space=2)."""
    widths, w = [], 0
    for kind, v in layout(parse(text)):
        if kind == 'char' or kind == 'full':
            w += 2
        elif kind == 'half':
            w += 1
        elif v[0] in LINE_END_BYTES or v[:2] == b'\xfe\x69':
            widths.append(w)
            w = 0
        else:
            w += insertion_width(v)
    return widths
