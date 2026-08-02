import struct
import sys

SRC = sys.argv[1] if len(sys.argv) > 1 else "nand_backup_1.bin"
PREFIX = sys.argv[2] if len(sys.argv) > 2 else "/tmp/fixed"

UBI_EC_MAGIC = b'UBI#'
UBI_VID_MAGIC = b'UBI!'
PEB_SIZE = 0x20000  # 128 KiB
DATA_OFFSET = 4096
LEB_SIZE = PEB_SIZE - DATA_OFFSET

with open(SRC, 'rb') as f:
    data = f.read()

pebs = []
for offset in range(0, len(data), PEB_SIZE):
    if data[offset:offset+4] != UBI_EC_MAGIC:
        continue
    vid_offset = offset + 2048
    if vid_offset + 64 > len(data):
        continue
    if data[vid_offset:vid_offset+4] != UBI_VID_MAGIC:
        continue
    vid_hdr = data[vid_offset:vid_offset+64]
    # correct ubi_vid_hdr layout: magic(4) version(1) vol_type(1) copy_flag(1) compat(1) vol_id(4) lnum(4) ...
    vol_type = vid_hdr[5]
    vol_id = struct.unpack('>I', vid_hdr[8:12])[0]
    lnum = struct.unpack('>I', vid_hdr[12:16])[0]
    data_size = struct.unpack('>I', vid_hdr[20:24])[0]
    pebs.append({'offset': offset, 'vol_id': vol_id, 'lnum': lnum, 'vol_type': vol_type, 'data_size': data_size})

volumes = {}
for p in pebs:
    volumes.setdefault(p['vol_id'], []).append(p)

print(f"Found {len(volumes)} UBI volumes in {SRC}: {sorted(volumes.keys())}")

for vol_id in sorted(volumes.keys()):
    if vol_id > 0x7FFFFFFF:
        print(f"Vol {vol_id}: internal UBI layout volume, skipping")
        continue
    vol_pebs = sorted(volumes[vol_id], key=lambda p: p['lnum'])
    vol_data = bytearray()
    for p in vol_pebs:
        start = p['offset'] + DATA_OFFSET
        vol_data.extend(data[start:start+LEB_SIZE])
    outname = f"{PREFIX}_vol{vol_id}.bin"
    with open(outname, 'wb') as f:
        f.write(vol_data)
    hsqs_idx = vol_data.find(b'hsqs')
    ubifs_magic = vol_data.find(b'\x31\x18\x10\x06')  # UBIFS_NODE_MAGIC little endian check
    types = sorted(set(p['vol_type'] for p in vol_pebs))
    print(f"Vol {vol_id}: {len(vol_pebs)} LEBs, {len(vol_data)} bytes, types={types} -> {outname}  hsqs@{hex(hsqs_idx) if hsqs_idx>=0 else 'none'}")
