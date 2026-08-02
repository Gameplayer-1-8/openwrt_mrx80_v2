# Tools

Small scripts used while porting. Most expect a NAND dump of **your own** device. Paths are
hard-coded near the top of each file, adjust them. Python 3 stdlib only, no dependencies.

The one exception is `mtdprobe.c`, which runs on the router itself. Cross-compile it with the
OpenWrt toolchain and copy it over:

```sh
STAGING=staging_dir/toolchain-aarch64_cortex-a53_gcc-14.4.0_musl
$STAGING/bin/aarch64-openwrt-linux-gcc -static -O2 -o mtdprobe tools/mtdprobe.c
cat mtdprobe | ssh root@192.168.1.1 'cat > /tmp/mtdprobe; chmod +x /tmp/mtdprobe'
ssh root@192.168.1.1 '/tmp/mtdprobe /dev/mtd8 0'
```

Use `cat | ssh` rather than `scp`, dropbear has no sftp-server.

| Script | What it does |
|---|---|
| `mtdprobe.c` | Reads one page twice, once through the ECC engine and once with `MTD_OPS_RAW`, and prints both. The raw read bypasses the ECC engine *and* the erased-page detector, so it shows what the chip actually puts on the wire. Buffers are pre-filled with `0xa5`, which keeps "the driver wrote `0xff`" distinguishable from "the driver never wrote anything". This is what identified the kernel 6.18 OTP problem. |
| `parse_mibib.py` | Decodes the MIBIB/smem partition table out of a raw NAND dump. This is how the authoritative offsets in `docs/hardware.md` were obtained. Do not trust a partition list from anywhere else. |
| `extract_ubi_volumes.py` | Extracts UBI volumes from a raw dump. Note the `ubi_vid_hdr` layout: `vol_id` is at bytes **8:12** and `lnum` at **12:16**. Getting that wrong invents dozens of phantom volumes and produces garbage, which cost a lot of time here. |
| `identify_bdf_variant.py` | Works out which OEM board-data variant belongs to a unit, by comparing the factory ART caldata against every candidate BDF. The factory writes the model's BDF template into ART and then fills in per-unit calibration, so the correct variant is the byte-wise closest one (99.9 % vs ~88 % for the wrong revision). |
| `verify_caldata.py` | Checks caldata carving against the offsets the OEM's own `read_caldata_to_fs.sh` uses. |
| `recover_ubifs_files.sh` | Reads files out of a UBIFS whose **UBI layer** is unreadable, by walking raw nodes (magic `0x06101831`): finds the directory entry by name, takes its inode number, then locates the matching data node. Useful when `ubiattach` fails with "both volume tables are corrupted", which on this device was actually a symptom of the wrong ECC strength, see the README. |
