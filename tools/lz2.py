"""LZ2-style codec used by the SA-1 decompressor at 00:B904.

Header byte: ccc lllll (length-1, commands 0-5), 111 ccc ll + byte (10-bit
length-1) or 110 ccc xx + two bytes (16-bit big-endian length-1); 0xFF ends
the stream.  Commands: 0 copy literal bytes, 1 byte fill,
2 alternating word fill, 3 increasing byte fill, 4-7 copy from an absolute
big-endian 16-bit offset of the output.
"""


def decompress(data, pos=0):
    out = bytearray()
    while True:
        h = data[pos]
        pos += 1
        if h == 0xFF:
            return bytes(out)
        if h >= 0xE0:
            cmd = (h >> 2) & 7
            n = ((h & 3) << 8 | data[pos]) + 1
            pos += 1
        elif h >= 0xC0:
            cmd = (h >> 2) & 7
            n = (data[pos] << 8 | data[pos + 1]) + 1
            pos += 2
        else:
            cmd = h >> 5
            n = (h & 0x1F) + 1
        if cmd == 0:
            out += data[pos:pos + n]
            pos += n
        elif cmd == 1:
            out += bytes([data[pos]]) * n
            pos += 1
        elif cmd == 2:
            a, b = data[pos], data[pos + 1]
            pos += 2
            out += bytes((a, b)[i & 1] for i in range(n))
        elif cmd == 3:
            v = data[pos]
            pos += 1
            out += bytes((v + i) & 0xFF for i in range(n))
        else:
            off = data[pos] << 8 | data[pos + 1]
            pos += 2
            for i in range(n):
                out.append(out[off + i])


def _header(cmd, n):
    n -= 1
    if n < 32 and cmd != 7:
        return bytes([cmd << 5 | n])
    return bytes([0xE0 | cmd << 2 | n >> 8, n & 0xFF])


MAX = 1024


def compress(src):
    out = bytearray()
    lit = bytearray()
    i, n = 0, len(src)
    index = {}

    def flush():
        while lit:
            chunk = lit[:MAX]
            out.extend(_header(0, len(chunk)) + chunk)
            del lit[:MAX]

    while i < n:
        best = (0, None, None)          # (gain, cmd, payload/length)
        # byte fill
        j = i
        while j < n and j - i < MAX and src[j] == src[i]:
            j += 1
        if j - i >= 3:
            best = max(best, (j - i - 2, 1, j - i), key=lambda t: t[0])
        # word fill
        if i + 1 < n:
            j = i + 2
            while j < n and j - i < MAX and src[j] == src[j - 2]:
                j += 1
            if j - i >= 4:
                best = max(best, (j - i - 3, 2, j - i), key=lambda t: t[0])
        # increasing fill
        j = i + 1
        while j < n and j - i < MAX and src[j] == (src[j - 1] + 1) & 0xFF:
            j += 1
        if j - i >= 3:
            best = max(best, (j - i - 2, 3, j - i), key=lambda t: t[0])
        # back reference (absolute offset < 0x10000)
        key = bytes(src[i:i + 3])
        for p in index.get(key, [])[-48:]:
            if p >= 0x10000:
                continue
            m = 0
            while i + m < n and m < MAX and src[p + m] == src[i + m]:
                m += 1
            if m >= 4 and m - 3 > best[0]:
                best = (m - 3, 4, (m, p))
        if best[1] is None:
            lit.append(src[i])
            step = 1
        else:
            flush()
            cmd = best[1]
            if cmd == 4:
                m, p = best[2]
                out.extend(_header(4, m) + bytes([p >> 8, p & 0xFF]))
                step = m
            elif cmd == 2:
                out.extend(_header(2, best[2]) + bytes(src[i:i + 2]))
                step = best[2]
            else:
                out.extend(_header(cmd, best[2]) + bytes([src[i]]))
                step = best[2]
        for k in range(i, min(i + step, n - 2)):
            index.setdefault(bytes(src[k:k + 3]), []).append(k)
        i += step
    flush()
    out.append(0xFF)
    return bytes(out)
