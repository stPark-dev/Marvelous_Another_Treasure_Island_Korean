"""Scene 0x54 riddle (アリのアシ／クモのアシ／トリのアシ／ゾウのハナ) in Korean.

The riddle is not part of the LZ map: 97:BBA0 composes it into the bottom-left
quadrant of map 78 (half 1) from 30 two-by-two "pieces".  Piece ids come from
the list at 97:BAC6 (file 0x2BBAC6, 6 x 5 words, read only for this scene);
each piece is four map entries (TL TR BL BR) at ED:0000 + id * 8.  Pieces
1CE-1DC belong to the riddle; 1B1/1B7 are the plain backgrounds of even/odd
piece rows.  Glyphs are one tile wide and two tall (8x16), red (colour 7) with
a dark edge (colour 4), over the grey noise of background tiles 00/10.

Tile window: asset 100 bytes 0-0xFFF (BG1 tiles 512-639), shared with scenes
4F-53, which compose digits into the same quadrant.  FREE_TILES are the kana
tiles only this scene shows plus two tiles none of 4F-54 show (runtime dumps,
docs/survey.md 6.7).

Columns keep the original places (map cols 8/11/14/17, read right to left):
코끼리 코 = ゾウのハナ, 새 다리 = トリのアシ, 거미 다리 = クモのアシ, 개미 다리 = アリのアシ.
"""
import scene_text

TILE_ASSET = 100
ID_LIST = 0x2BBAC6                 # 97:BAC6
PIECES = 0x2D0000                  # ED:0000
OWN_PIECES = list(range(0x1CE, 0x1DD))
BG_PIECES = {0: 0x1B1, 1: 0x1B7}   # by piece-row parity
FREE_TILES = [0x4A, 0x4B, 0x4C, 0x4D, 0x4E, 0x4F, 0x5A, 0x5B, 0x5C, 0x5D, 0x5E, 0x5F,
              0x6A, 0x6B, 0x6C, 0x6D, 0x6E, 0x6F, 0x7A, 0x7B, 0x7C, 0x7D, 0x7E, 0x7F]
ATTR = 0x1C00                      # palette 7
STROKE, EDGE = 7, 4
# (grid column 0-11 = map cols 7-18, text by piece row); ' ' = background
COLUMNS = [(1, '개미 다리'), (4, '거미 다리'), (7, '새  다리'), (10, '코끼리 코')]


# hand-drawn 7x14 syllables (1 px strokes; the edge colour adds the second pixel)
GLYPHS = {
    '개': ['....#.#', '###.#.#', '..#.#.#', '..#.#.#', '..#.#.#', '..#.###', '..#.#.#',
           '.#..#.#', '.#..#.#', '#...#.#', '....#.#', '....#.#', '....#.#', '....#.#'],
    '미': ['......#', '####..#', '#..#..#', '#..#..#', '#..#..#', '#..#..#', '#..#..#',
           '#..#..#', '#..#..#', '####..#', '......#', '......#', '......#', '......#'],
    '다': ['.....#.', '####.#.', '#....#.', '#....#.', '#....#.', '#....##', '#....#.',
           '#....#.', '####.#.', '.....#.', '.....#.', '.....#.', '.....#.', '.....#.'],
    '리': ['......#', '####..#', '...#..#', '...#..#', '####..#', '#.....#', '#.....#',
           '####..#', '......#', '......#', '......#', '......#', '......#', '......#'],
    '거': ['......#', '####..#', '...#..#', '...#..#', '...#..#', '...#.##', '..#...#',
           '.#....#', '#.....#', '......#', '......#', '......#', '......#', '......#'],
    '새': ['....#.#', '.#..#.#', '.#..#.#', '.#..#.#', '.#..#.#', '#.#.###', '#.#.#.#',
           '....#.#', '....#.#', '....#.#', '....#.#', '....#.#', '....#.#', '....#.#'],
    '코': ['######.', '.....#.', '.....#.', '######.', '.....#.', '.....#.', '.....#.',
           '.......', '.......', '...#...', '...#...', '#######', '.......', '.......'],
    '끼': ['......#', '##.##.#', '.#..#.#', '.#..#.#', '.#..#.#', '.#..#.#', '.#..#.#',
           '.#..#.#', '#..#..#', '......#', '......#', '......#', '......#', '......#'],
}


def glyph_mask(ch):
    return GLYPHS[ch]


def _glyph_tiles(ch, tiles):
    """Two 4bpp tiles (top, bottom) for one syllable over background tiles 00/10."""
    px = [row[:] for k in (0x00, 0x10) for row in scene_text._tile_pixels(tiles, k)]
    mask = glyph_mask(ch)
    on = {(x, y + 1) for y, row in enumerate(mask) for x, c in enumerate(row) if c == '#'}
    for x, y in on:
        # lower-right edge, but never inside a 1 px gap (it would join the two strokes)
        if (x + 1, y + 1) not in on and (x + 2, y + 1) not in on and x + 1 < 8 and y + 1 < 16:
            px[y + 1][x + 1] = EDGE
    for x, y in on:
        px[y][x] = STROKE
    return scene_text._tile_bytes(px[:8]), scene_text._tile_bytes(px[8:])


def glyph_tiles():
    """{syllable: (top tile, bottom tile)} in FREE_TILES order."""
    chars = sorted(set(''.join(t for _, t in COLUMNS)) - {' '}, key=lambda c: ''.join(t for _, t in COLUMNS).index(c))
    if 2 * len(chars) > len(FREE_TILES):
        raise ValueError('riddle needs %d tiles' % (2 * len(chars)))
    return {ch: (FREE_TILES[2 * i], FREE_TILES[2 * i + 1]) for i, ch in enumerate(chars)}


def build(rom):
    """Return (new tile asset 100, {file offset: bytes}) for the piece list and pieces."""
    import lz2
    tiles = bytearray(lz2.decompress(rom, scene_text.asset_offset(rom, TILE_ASSET)))
    tile_of = glyph_tiles()
    for ch, (top, bottom) in tile_of.items():
        a, b = _glyph_tiles(ch, tiles)
        tiles[top * 32:top * 32 + 32] = a
        tiles[bottom * 32:bottom * 32 + 32] = b

    cells = [[0x20 * (r // 2 % 2) + 0x10 * (r % 2) + (c % 2) for c in range(12)] for r in range(10)]
    for col, text in COLUMNS:
        for pr, ch in enumerate(text):
            if ch != ' ':
                cells[pr * 2][col], cells[pr * 2 + 1][col] = tile_of[ch]
    ids, defs = [], {}
    free_ids = list(OWN_PIECES)
    for pr in range(5):
        bg = tuple(0x20 * (pr % 2) + k for k in (0x00, 0x01, 0x10, 0x11))
        for pc in range(6):
            piece = (cells[pr * 2][pc * 2], cells[pr * 2][pc * 2 + 1],
                     cells[pr * 2 + 1][pc * 2], cells[pr * 2 + 1][pc * 2 + 1])
            if piece == bg:
                ids.append(BG_PIECES[pr % 2])
                continue
            if piece not in defs:
                if not free_ids:
                    raise ValueError('riddle needs more than %d pieces' % len(OWN_PIECES))
                defs[piece] = free_ids.pop(0)
            ids.append(defs[piece])
    writes = {ID_LIST: b''.join(i.to_bytes(2, 'little') for i in ids)}
    for piece, pid in defs.items():
        writes[PIECES + pid * 8] = b''.join((ATTR | 0x200 | t).to_bytes(2, 'little') for t in piece)
    return bytes(tiles), writes
