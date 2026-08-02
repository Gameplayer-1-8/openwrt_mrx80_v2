"""Verify caldata carving against the offsets the OEM firmware actually uses.

From /lib/read_caldata_to_fs.sh (ap-mp03.5* case, IPQ5018 + qcn6122):
    IPQ5018 caldata : skip=4096   (0x1000)  count=FILESIZE (=131072)
    qcn6122 caldata1: skip=157696 (0x26800) count=FILESIZE (=131072)
    qcn6122 caldata2: skip=311296 (0x4C000) count=FILESIZE
"""
import os

SIZE = 131072
OFF_IPQ = 4096
OFF_QCN1 = 157696
OFF_QCN2 = 311296

with open("art.bin", "rb") as f:
    art = f.read()

print(f"art.bin = {len(art)} bytes\n")


def summarize(name, data):
    hdr = " ".join(f"{b:02x}" for b in data[:16])
    tail_ff = 0
    for b in reversed(data):
        if b != 0xFF:
            break
        tail_ff += 1
    nonff = sum(1 for b in data if b != 0xFF)
    print(f"{name}: {len(data)} bytes")
    print(f"  header : {hdr}")
    print(f"  0x38   : {' '.join(f'{b:02x}' for b in data[0x38:0x40])}")
    print(f"  0x40   : {' '.join(f'{b:02x}' for b in data[0x40:0x48])}")
    print(f"  non-FF : {nonff}, trailing FF: {tail_ff}")
    valid = data[:4] == b"\x01\x00\x04\x04"
    print(f"  valid QCA bdwlan/caldata header: {valid}")
    print()


regions = {
    "caldata_ipq5018 @0x1000": art[OFF_IPQ:OFF_IPQ + SIZE],
    "caldata_qcn6122_1 @0x26800": art[OFF_QCN1:OFF_QCN1 + SIZE],
    "caldata_qcn6122_2 @0x4C000": art[OFF_QCN2:OFF_QCN2 + SIZE],
}
for name, data in regions.items():
    summarize(name, data)

# write the correctly-carved caldata
with open("caldata_ipq5018_correct.bin", "wb") as f:
    f.write(regions["caldata_ipq5018 @0x1000"])
with open("caldata_qcn6122_correct.bin", "wb") as f:
    f.write(regions["caldata_qcn6122_1 @0x26800"])
print("wrote caldata_ipq5018_correct.bin / caldata_qcn6122_correct.bin\n")

# compare against what the build currently uses
for existing, correct_key in (
    ("art_ipq5018.bin", "caldata_ipq5018 @0x1000"),
    ("art_qcn6122.bin", "caldata_qcn6122_1 @0x26800"),
):
    if not os.path.exists(existing):
        continue
    with open(existing, "rb") as f:
        cur = f.read()
    ref = regions[correct_key]
    match = cur == ref
    print(f"{existing} vs {correct_key}: {'IDENTICAL' if match else 'DIFFERENT'}")
    if not match:
        first = next((i for i in range(min(len(cur), len(ref))) if cur[i] != ref[i]), None)
        print(f"   sizes {len(cur)} vs {len(ref)}, first diff at {hex(first) if first is not None else 'n/a'}")
        # is it merely shifted?
        for shift in (2048, -2048, 0x800, -0x800):
            off = OFF_QCN1 + shift if "qcn" in existing else OFF_IPQ + shift
            if 0 <= off and off + SIZE <= len(art) and art[off:off + SIZE] == cur:
                print(f"   -> current file was actually carved at {hex(off)} (shift {shift})")
