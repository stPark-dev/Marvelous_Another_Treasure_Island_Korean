"""Final-write planning: every byte the product build changes is declared once.

A write records its owner, offset, data and optionally the source bytes it
expects to replace.  Overlaps between writers, writes into protected ranges and
any difference between source and output that no write explains are errors.
"""


class PlanError(ValueError):
    pass


class WritePlan:
    def __init__(self, src, size=None, fill=0xFF):
        self.src = bytes(src)
        self.size = size or len(src)
        if self.size < len(src):
            raise PlanError('output smaller than source')
        self.fill = fill
        self.writes = []        # (offset, data, owner)
        self.protected = []     # (start, end, name)

    def protect(self, name, start, end):
        self.protected.append((start, end, name))

    def patch(self, owner, offset, data, expect=None):
        data = bytes(data)
        end = offset + len(data)
        if offset < 0 or end > self.size:
            raise PlanError('%s: write %X+%X outside output' % (owner, offset, len(data)))
        if expect is not None:
            if self.src[offset:offset + len(expect)] != bytes(expect):
                raise PlanError('%s: source bytes at %X are %s, expected %s' % (
                    owner, offset, self.src[offset:offset + len(expect)].hex(), bytes(expect).hex()))
        for s, e, name in self.protected:
            if offset < e and s < end:
                raise PlanError('%s: write %X..%X hits protected %s' % (owner, offset, end, name))
        for o, d, who in self.writes:
            if offset < o + len(d) and o < end:
                raise PlanError('%s: write %X..%X overlaps %s at %X..%X' % (owner, offset, end, who, o, o + len(d)))
        self.writes.append((offset, data, owner))

    def apply(self):
        out = bytearray(self.src) + bytes([self.fill]) * (self.size - len(self.src))
        for o, d, _ in self.writes:
            out[o:o + len(d)] = d
        return bytes(out)

    def coverage(self):
        cov = bytearray(self.size)
        for o, d, _ in self.writes:
            cov[o:o + len(d)] = b'\x01' * len(d)
        return cov


def verify(src, out, plan):
    """Fail on any output byte that differs from source/fill and no write declared."""
    if len(out) != plan.size:
        raise PlanError('output size %X != planned %X' % (len(out), plan.size))
    cov = plan.coverage()
    n = len(src)
    bad = [i for i in range(len(out))
           if not cov[i] and out[i] != (src[i] if i < n else plan.fill)]
    if bad:
        raise PlanError('%d unexplained bytes, first at %X' % (len(bad), bad[0]))
