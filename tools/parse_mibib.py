"""Parse the MIBIB (smem) partition table from the NAND dump.

struct smem_ptable {
    __le32 magic[2];   // 0x55EE73AA, 0xE35EBDDB
    __le32 version;    // 4
    __le32 len;        // number of partitions
    struct smem_ptn parts[];
};
struct smem_ptn {          // 28 bytes
    char   name[16];
    __le32 start;          // in erase blocks
    __le32 size;           // in erase blocks (0xFFFFFFFF = rest of flash)
    __le32 attr;
};
"""
import struct

SRC = "nand_backup_1.bin"
BLK = 0x20000  # 128K erase block

with open(SRC, "rb") as f:
    data = f.read()

MAGIC = struct.pack("<II", 0x55EE73AA, 0xE35EBDDB)

positions = []
start = 0
while True:
    i = data.find(MAGIC, start)
    if i < 0:
        break
    positions.append(i)
    start = i + 1

for pos in positions:
    version, numparts = struct.unpack("<II", data[pos + 8:pos + 16])
    if version != 4 or not (0 < numparts <= 48):
        continue
    print(f"=== partition table at {hex(pos)}: version={version}, {numparts} partitions ===")
    print(f"{'#':>2}  {'name':<16s} {'offset':>12s} {'size':>12s}  attr")
    for n in range(numparts):
        off = pos + 16 + n * 28
        raw = data[off:off + 28]
        if len(raw) < 28:
            break
        name = raw[:16].split(b"\x00")[0].decode(errors="replace")
        start_blk, size_blk, attr = struct.unpack("<III", raw[16:28])
        if size_blk == 0xFFFFFFFF:
            size_str = "to-end"
            size_bytes = len(data) - start_blk * BLK
        else:
            size_bytes = size_blk * BLK
            size_str = f"{size_bytes // 1024}K"
        print(f"{n:2d}  {name:<16s} {hex(start_blk * BLK):>12s} {size_str:>12s}  {hex(attr)}")
    print()
