# Hardware notes

## NAND layout

Parsed from the MIBIB with `tools/parse_mibib.py`. This is the authoritative source.

| Partition | Offset | Size |
|---|---|---|
| `0:SBL1` | 0x0 | 512K |
| `0:MIBIB` | 0x80000 | 512K |
| `0:BOOTCONFIG` / `0:BOOTCONFIG1` | 0x100000 / 0x140000 | 256K each |
| `0:QSEE` | 0x180000 | 1M |
| `0:DEVCFG` | 0x280000 | 256K |
| `0:CDT` | 0x2c0000 | 256K |
| `0:APPSBLENV` | 0x300000 | 512K |
| `0:APPSBL` | 0x380000 | 1280K |
| `0:ART` | 0x4c0000 | 1M |
| `0:TRAINING` | 0x5c0000 | 512K |
| `rootfs` | 0x640000 | 43008K |
| `rootfs_1` | 0x3040000 | 43008K |
| `tp_data` | 0x5a40000 | 8448K |
| `radio` | 0x6280000 | 4352K |
| `data` | 0x66c0000 | 512K |

`sysupgrade` writes `rootfs`. `0:BOOTCONFIG` parses as `rootfs primaryboot=0`, so the
bootloader uses that half; `rootfs_1` keeps the OEM image untouched. `0:SBL1` and `0:APPSBL`
are never written, so U-Boot always survives and TFTP recovery stays available.

## Calibration data in `0:ART`

Offsets taken from the OEM's own `/lib/read_caldata_to_fs.sh`, case `ap-mp03.5*`:

```
IPQ5018 caldata   0x1000    131072 bytes  ->  cal-ahb-c000000.wifi.bin
QCN6122 caldata   0x26800   131072 bytes  ->  cal-ahb-b00a040.wifi.bin
(a third region at 0x4C000 is all 0xFF and unused)
```

Extracted at runtime by `11-ath11k-caldata`. The caldata carries only the Atheros placeholder
MAC `00:03:7f:12:34:56`, so the radios' addresses are patched from the label MAC.

**`0:ART` contains no MAC on this device.** Those bytes read `0xff`, and U-Boot says
`eth0 MAC Address from ART is not valid`. Do not wire `nvmem-cells` to it.

## `tp_data`

A UBI volume holding a UBIFS with the factory identity data:

```
ap-config  default-mac  device-id  pin  product-info  router-config  user-config
```

`default-mac` is six raw bytes. `product-info` is plain text:

```
vendor_name:Mercusys        product_name:MR3000X
device_name:AX3000 Dual-Band Wi-Fi 6 Router
country:DE   hw_ver:00000002   special_id:45550000   product_id:02130002
```

If `ubiattach` reports "both volume tables are corrupted", check the ECC strength before
concluding the partition is damaged. With `nand-ecc-strength = <8>` this volume looks
destroyed and mounts fine at `<4>`.

## Board data files

The `.bXX` suffix on the OEM BDFs is the board_id in hex, and the factory caldata carries the
same board_id at offset 0x3a: `0x24` for the IPQ5018 region, `0x60` for QCN6122. Comparing the
caldata byte-wise against each candidate then identifies region and revision: EU/`default`
matches 99.98 % and 99.95 %, revision `00000001` only ~88 %.

The EU `default` files are byte-identical across MR80X, MR3000X, MR1800X and MR70X
(md5 `bbcd52a165e477221404164eb3d82344` / `503daccafc8e25573593f70b3297f2fc`).

## U-Boot

```
U-Boot 2016.01 (Sep 20 2024)   machid 8040000   bootcmd=bootipq   bootdelay=1
Serial NAND: ESMT F50D1G41LB, 128 MiB, page 2048, spare 64, ECC 4-bit
```

`0:APPSBLENV` has a bad CRC on this unit, so U-Boot falls back to its built-in environment on
every boot, so `ipaddr`/`serverip` have to be set each time unless you `saveenv`.

Note that `Net:` initialisation, which includes `rtk_switch_init` for the RTL8367S, only runs
when U-Boot falls through to its prompt. Autoboot into NAND never touches the switch. See the
main README.
