#!/bin/bash
# The UBI volume table on tp_data is corrupt so it cannot be attached, but the UBIFS
# content underneath is intact - the bytes around the "default-mac" string are UBIFS
# node headers (magic 0x06101831). Walk the raw partition node by node, find the
# directory entry named default-mac, take its inode number, then find the data node
# carrying that inode's contents.
python3 - /tmp/tp_data.bin <<'PY'
import struct, sys, zlib

d = open(sys.argv[1], 'rb').read()
MAGIC = 0x06101831
INO, DATA, DENT = 0, 1, 2

dents, datas, inos = {}, {}, {}
off, n = 0, 0
while True:
    i = d.find(struct.pack('<I', MAGIC), off)
    if i < 0:
        break
    off = i + 4
    if i + 24 > len(d):
        break
    magic, crc, sqnum, ln, ntype, gtype = struct.unpack('<IIQIBB', d[i:i+22])
    if ln < 24 or ln > 65536 or i + ln > len(d):
        continue
    n += 1
    node = d[i:i+ln]
    if ntype == DENT and ln > 44:
        inum = struct.unpack('<Q', node[40:48])[0]
        nlen = struct.unpack('<H', node[50:52])[0]
        name = node[56:56+nlen].decode('utf-8', 'replace')
        dents.setdefault(name, set()).add(inum)
    elif ntype == DATA and ln > 48:
        key_inum = struct.unpack('<I', node[24:28])[0]
        size, compr = struct.unpack('<IH', node[40:44] + node[44:46])
        datas.setdefault(key_inum, []).append((sqnum, size, compr, node[48:ln]))
    elif ntype == INO and ln > 40:
        key_inum = struct.unpack('<I', node[24:28])[0]
        inos[key_inum] = struct.unpack('<Q', node[56:64])[0] if ln > 64 else None

print(f"scanned {n} UBIFS nodes")
print(f"directory entries found: {len(dents)}")
for name in sorted(dents):
    print(f"   {name:<22s} inode {sorted(dents[name])}")

def inflate(compr, payload, size):
    if compr == 0:
        return payload[:size]
    if compr == 2:
        try:
            return zlib.decompressobj(-zlib.MAX_WBITS).decompress(payload)[:size]
        except Exception:
            return None
    return None      # 1 = LZO, 3 = zstd: not available in the stdlib

print()
for name in sorted(dents):
    for inum in sorted(dents[name]):
        chunks = datas.get(inum)
        if not chunks:
            continue
        sqnum, size, compr, payload = max(chunks)     # newest version of the node
        out = inflate(compr, payload, size)
        tag = {0: 'none', 1: 'lzo', 2: 'zlib', 3: 'zstd'}.get(compr, str(compr))
        print(f"--- {name} (inode {inum}, {size} bytes, compr={tag}) ---")
        if out is None:
            print("    could not decompress; raw first 64 bytes:")
            print("   ", payload[:64].hex(' '))
        else:
            print("    hex :", out[:64].hex(' '))
            print("    text:", ''.join(chr(c) if 32 <= c < 127 else '.' for c in out[:64]))
            if size >= 6:
                print("    as MAC (first 6 bytes):",
                      ':'.join('%02x' % b for b in out[:6]))
        print()
PY
