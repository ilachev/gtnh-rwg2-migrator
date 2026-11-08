"""Anvil region access with raw compressed chunk preservation."""
import gzip
import re
import struct
import zlib
from dataclasses import dataclass
from pathlib import Path
from . import nbt

NAME = re.compile(r'r\.(-?\d+)\.(-?\d+)\.mca$')
GROUND = {1, 2, 3, 7, 12, 13, 14, 15, 16, 21, 24, 56, 73, 74, 82, 87, 88, 110, 129, 159, 172, 174}


@dataclass
class Chunk:
    x: int
    z: int
    timestamp: bytes
    record: bytes

    def decode(self):
        kind, payload = self.record[4], self.record[5:]
        if kind == 1:
            data = gzip.decompress(payload)
        elif kind == 2:
            obj = zlib.decompressobj()
            data = obj.decompress(payload, nbt.MAX_BYTES + 1)
            if obj.unconsumed_tail or not obj.eof:
                raise ValueError("Invalid or oversized compressed chunk")
        elif kind == 3:
            data = payload
        else:
            raise ValueError("Unsupported Anvil compression (including external chunks)")
        result = nbt.loads(data)
        return result.get('Level', result)


def read(path):
    path = Path(path)
    match = NAME.fullmatch(path.name)
    if not match:
        raise ValueError("Invalid region filename")
    rx, rz = map(int, match.groups())
    raw = path.read_bytes()
    if len(raw) < 8192 or len(raw) % 4096:
        raise ValueError("Truncated region: " + path.name)
    used = {0, 1}
    chunks = []
    for i in range(1024):
        location = struct.unpack_from('>I', raw, i * 4)[0]
        if not location:
            continue
        offset, sectors = location >> 8, location & 255
        if offset < 2 or not sectors or (offset + sectors) * 4096 > len(raw):
            raise ValueError("Invalid region location: " + path.name)
        allocated = set(range(offset, offset + sectors))
        if allocated & used:
            raise ValueError("Overlapping Anvil sectors: " + path.name)
        used.update(allocated)
        length = struct.unpack_from('>I', raw, offset * 4096)[0]
        if length < 1 or length + 4 > sectors * 4096:
            raise ValueError("Invalid chunk record length")
        record = raw[offset * 4096:offset * 4096 + length + 4]
        if record[4] not in (1, 2, 3):
            raise ValueError("External or unsupported chunk compression")
        chunks.append(Chunk(rx * 32 + i % 32, rz * 32 + i // 32,
                            raw[4096 + i * 4:4100 + i * 4], record))
    return chunks


def write(path, chunks):
    header = bytearray(8192)
    body = bytearray()
    seen = set()
    path = Path(path)
    rx, rz = map(int, NAME.fullmatch(path.name).groups())
    for chunk in chunks:
        if chunk.x // 32 != rx or chunk.z // 32 != rz:
            raise ValueError("Chunk belongs to another region")
        slot = (chunk.z % 32) * 32 + chunk.x % 32
        if slot in seen:
            raise ValueError("Duplicate chunk")
        seen.add(slot)
        offset = 2 + len(body) // 4096
        sectors = (len(chunk.record) + 4095) // 4096
        if sectors > 255:
            raise ValueError("Chunk is too large for Anvil")
        struct.pack_into('>I', header, slot * 4, offset * 256 + sectors)
        header[4096 + slot * 4:4100 + slot * 4] = chunk.timestamp
        body.extend(chunk.record)
        body.extend(bytes(sectors * 4096 - len(chunk.record)))
    path.write_bytes(header + body)
    actual = {(c.x, c.z): (c.timestamp, c.record) for c in read(path)}
    expected = {(c.x, c.z): (c.timestamp, c.record) for c in chunks}
    if actual != expected:
        raise ValueError("Raw retained chunk verification failed")


def ground(data, x, z):
    sections = {s['Y']: s for s in data.get('Sections', [])}
    top = min(255, data.get('HeightMap', [256] * 256)[z * 16 + x] - 1)
    for y in range(top, -1, -1):
        section = sections.get(y // 16)
        if not section:
            continue
        i = y % 16 * 256 + z * 16 + x
        if 'Blocks16' in section:
            block = struct.unpack_from('>H', section['Blocks16'], i * 2)[0]
        else:
            block = section['Blocks'][i]
            for key, shift in [('Add', 8), ('BlocksB2Hi', 12)]:
                if key in section:
                    block |= ((section[key][i // 2] >> ((i % 2) * 4)) & 15) << shift
        if block in GROUND:
            return y
    raise ValueError("No recognizable natural ground at sampled boundary")
