"""Ending staff credits: Korean job titles, names kept (D14).

LZ asset 62 is a 2bpp sheet of 128 glyphs (16x16 = tiles TL, TL+1, TL+16,
TL+17 with TL = (g // 8) * 32 + (g % 8) * 2).  LZ asset 63 lists the credits
as one map entry per glyph (palette 3 | TL tile), 32 per row, 0x1EE = blank;
rows 0-47 are the roll, the rest is unused filler.  Title glyphs whose
katakana no name uses are redrawn as Hangul (Galmuri11-Bold, colour 2 with a
colour 1 outline like the originals); デバックチーム, SMC and the ー in
尾崎裕ー stay because they belong to names.
"""
import scene_text

SHEET_ASSET, MAP_ASSET = 62, 63
ROWS = 48
BLANK = 0x1EE
GLYPHS = ('グラフィック小野' '塚英二高充浩士山' '芳紀三島幹雄松原' '祥サウンド尾崎裕'
          'ーメイプロム副康' '成西達夫葛貴光ブ' '笠栄弘竹谷範佐々' '木誠住吉伸啓樽角'
          '真澄テゼニカルポ' 'ト池田昭中郷俊彦' 'タパケジデザ古庄' '井澤圭スペシャ能'
          '登司本佳坂哲哉勝' 'レュ上村雅之内溥' 'ゴ・子SMCバチ' 'エ中章人オェ＿＿')
DOT = GLYPHS.index('・')
TITLES = {
    0: '그래픽',                       # グラフィック
    4: '사운드',                       # サウンド
    8: '메인　프로그램',               # メイン　プログラム
    12: '오브젝트　프로그램',          # オブジェクト　プログラム
    16: '프로그램',                    # プログラム
    20: '기술　지원',                  # テクニカル　サポート
    24: '타이틀　로고·패키지　디자인',  # タイトルロゴ・パッケージ　デザイン
    28: '특별　감사',                  # スペシャル　サンクス (fits the 36 free glyph slots)
    32: '서브　디렉터',                # サブ　ディレクター
    36: '디렉터',                      # ディレクター
    40: '프로듀서',                    # プロデューサー
    44: '총괄　프로듀서',              # エクゼクティブ　プロデューサー
}


def glyph_tiles(g):
    tl = (g // 8) * 32 + (g % 8) * 2
    return tl, tl + 1, tl + 16, tl + 17


def _entries(cmap):
    return [cmap[2 * i] | cmap[2 * i + 1] << 8 for i in range(len(cmap) // 2)]


def _glyph_of(entry):
    n = entry & 0x3FF
    return None if n == BLANK else (n // 32) * 8 + (n % 32) // 2


def decode(cmap, chars=GLYPHS):
    ent = _entries(cmap)
    return [''.join('　' if _glyph_of(e) is None else chars[_glyph_of(e)] for e in ent[r * 32:r * 32 + 32])
            for r in range(ROWS)]


def name_glyphs(cmap):
    ent = _entries(cmap)
    return {_glyph_of(e) for r in range(ROWS) if r not in TITLES for e in ent[r * 32:r * 32 + 32]} - {None}


def assignment(cmap):
    """{Hangul syllable: glyph slot}, using slots no name needs."""
    keep = name_glyphs(cmap) | {DOT}
    free = [g for g in range(128) if g not in keep and glyph_tiles(g)[0] != BLANK]   # slot 127 is the blank
    syllables = []
    for text in TITLES.values():
        for ch in text:
            if '가' <= ch <= '힣' and ch not in syllables:
                syllables.append(ch)
    if len(syllables) > len(free):
        raise ValueError('credits need %d glyph slots, %d free' % (len(syllables), len(free)))
    return dict(zip(syllables, free))


def glyph_chars(cmap):
    chars = list(GLYPHS)
    chars[DOT] = '·'
    for ch, g in assignment(cmap).items():
        chars[g] = ch
    return ''.join(chars)


def glyph_pixels(sheet, g):
    px = [[0] * 16 for _ in range(16)]
    for j, tn in enumerate(glyph_tiles(g)):
        for y in range(8):
            lo, hi = sheet[tn * 16 + 2 * y], sheet[tn * 16 + 2 * y + 1]
            for x in range(8):
                px[(j // 2) * 8 + y][(j % 2) * 8 + x] = ((lo >> (7 - x)) & 1) | (((hi >> (7 - x)) & 1) << 1)
    return px


def _render(ch, bdf):
    g = bdf[ord(ch)]
    w, h, bx, by = g['bbx']
    nbits = ((w + 7) // 8) * 8
    x0, top = 1 + (14 - w) // 2, 2 + (11 - (by + h))
    on = {(x0 + xx, top + yy) for yy, row in enumerate(g['rows']) for xx in range(w)
          if (row >> (nbits - 1 - xx)) & 1}
    px = [[0] * 16 for _ in range(16)]
    for x, y in on:
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                px[y + dy][x + dx] = 1
    for x, y in on:
        px[y][x] = 2
    return px


def _put(sheet, g, px):
    for j, tn in enumerate(glyph_tiles(g)):
        for y in range(8):
            lo = hi = 0
            for x in range(8):
                v = px[(j // 2) * 8 + y][(j % 2) * 8 + x]
                lo |= (v & 1) << (7 - x)
                hi |= (v >> 1) << (7 - x)
            sheet[tn * 16 + 2 * y], sheet[tn * 16 + 2 * y + 1] = lo, hi


def build(sheet, cmap, bdf=None):
    """Return (new glyph sheet, new credits map)."""
    bdf = bdf or scene_text._font(scene_text.BOLD_BDF)
    slots = assignment(cmap)
    new_sheet = bytearray(sheet)
    for ch, g in slots.items():
        _put(new_sheet, g, _render(ch, bdf))
    ent = _entries(cmap)
    for row, text in TITLES.items():
        start = (32 - len(text)) // 2
        for c in range(32):
            e = ent[row * 32 + c]
            k = c - start
            ch = text[k] if 0 <= k < len(text) else '　'
            g = None if ch == '　' else (DOT if ch == '·' else slots[ch])
            ent[row * 32 + c] = (e & 0xFC00) | (BLANK if g is None else glyph_tiles(g)[0])
    new_map = b''.join(e.to_bytes(2, 'little') for e in ent)
    return bytes(new_sheet), new_map
