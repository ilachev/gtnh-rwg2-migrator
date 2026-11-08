"""Small bounded NBT reader; generator edits preserve all unrelated payload bytes."""
import gzip
import io
import struct

MAX_BYTES = 64 * 1024 * 1024


class Reader:
    def __init__(self, raw):
        if len(raw) > MAX_BYTES:
            raise ValueError("NBT document exceeds 64 MiB")
        self.raw = raw
        self.f = io.BytesIO(raw)
        self.spans = {}

    def take(self, n):
        if n < 0 or n > MAX_BYTES:
            raise ValueError("Invalid NBT length")
        b = self.f.read(n)
        if len(b) != n:
            raise ValueError("Truncated NBT document")
        return b

    def num(self, fmt):
        return struct.unpack(fmt, self.take(struct.calcsize(fmt)))[0]

    def string(self):
        # Existing strings are not rewritten, including Java modified-UTF8 strings.
        return self.take(self.num('>H')).decode('utf-8', errors='replace')

    def value(self, typ, path=(), depth=0):
        if depth > 64:
            raise ValueError("NBT nesting exceeds 64 levels")
        start = self.f.tell()
        if typ in (1, 2, 3, 4, 5, 6):
            v = self.num({1: '>b', 2: '>h', 3: '>i', 4: '>q', 5: '>f', 6: '>d'}[typ])
        elif typ == 8:
            v = self.string()
        elif typ in (7, 11, 12):
            count = self.num('>i')
            size = {7: 1, 11: 4, 12: 8}[typ]
            b = self.take(count * size)
            v = b if typ == 7 else list(struct.unpack('>' + ('i' if typ == 11 else 'q') * count, b))
        elif typ == 9:
            sub, count = self.num('>B'), self.num('>i')
            if not 0 <= count <= 1000000 or (sub == 0 and count):
                raise ValueError("Invalid NBT list")
            v = [self.value(sub, path + (i,), depth + 1) for i in range(count)]
        elif typ == 10:
            v = {}
            while True:
                sub = self.num('>B')
                if not sub:
                    break
                name = self.string()
                if name in v:
                    raise ValueError("Duplicate NBT compound key")
                v[name] = self.value(sub, path + (name,), depth + 1)
        else:
            raise ValueError("Unsupported NBT type: " + str(typ))
        if path in [('Data', 'generatorName'), ('Data', 'generatorVersion'), ('Data', 'generatorOptions')]:
            self.spans[path[-1]] = (start, self.f.tell(), typ)
        return v

    def parse(self):
        typ = self.num('>B')
        if typ != 10:
            raise ValueError("NBT root must be a compound")
        self.string()
        result = self.value(typ)
        if self.f.read(1):
            raise ValueError("Unexpected bytes after NBT root")
        return result


def unpack(data):
    if data[:2] == b'\x1f\x8b':
        with gzip.GzipFile(fileobj=io.BytesIO(data)) as stream:
            data = stream.read(MAX_BYTES + 1)
    return Reader(data)


def loads(data):
    return unpack(data).parse()


def rwg2_level(data):
    reader = unpack(data)
    reader.parse()
    name = b'RWG2_CONTINENTS'
    replacements = {
        'generatorName': (8, struct.pack('>H', len(name)) + name),
        'generatorVersion': (3, struct.pack('>i', 0)),
        'generatorOptions': (8, b'\0\0'),
    }
    if reader.spans.keys() != replacements.keys():
        raise ValueError("Missing world generator fields")
    raw = reader.raw
    for key, (start, end, typ) in sorted(reader.spans.items(), key=lambda item: item[1][0], reverse=True):
        expected, payload = replacements[key]
        if expected != typ:
            raise ValueError("Unexpected generator field type")
        raw = raw[:start] + payload + raw[end:]
    return gzip.compress(raw, mtime=0)
