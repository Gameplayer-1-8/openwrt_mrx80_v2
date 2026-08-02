# OpenWrt for the Mercusys MR3000X (sold/branded MR80X v2)

Working OpenWrt port for a Qualcomm IPQ5018 based Mercusys router, built against OpenWrt main
(`ce16dd8`, kernel 6.12.100). Everything below was verified on real hardware.

> **Read the "Before you use this" section.** The MAC address is currently hard-coded in the
> DTS for one specific unit. You *will* want to change that.

---

## Device

| | |
|---|---|
| Marketing name | Mercusys MR3000X / AX3000 Dual-Band Wi-Fi 6 Router |
| OpenWrt name | `mercusys,mr80x-v2` |
| SoC | Qualcomm IPQ5018, dual Cortex-A53 @ 1.008 GHz |
| RAM | 256 MB |
| Flash | 128 MB SPI-NAND, ESMT **F50D1G41LB**, **4-bit ECC** |
| WiFi 2.4 GHz | IPQ5018 built-in (`c000000.wifi`), ath11k |
| WiFi 5 GHz | QCN6122 (`b00a040.wifi`), ath11k multipd, userpd 2 |
| Switch | Realtek **RTL8367S** on MDIO1, DSA (`rtl8365mb`) |
| CPU ↔ switch | SGMII **1 Gbit** on switch port 6 |
| Serial | 115200 8N1, `blsp1_uart1` @ 0x78af000 |

The unit's own `product-info` in the `tp_data` partition reads `product_name:MR3000X`,
`hw_ver:00000002`, `special_id:45550000` (EU). The EU board-data files for MR80X and MR3000X
are byte-identical, so the naming ambiguity does not matter in practice.

## Status

Working: both radios, DSA switch with `wan`/`lan1`/`lan2`/`lan3`, LuCI, sysupgrade, boot from
NAND, serial console (in and out), per-unit WiFi calibration read from flash at runtime.

~50 MB RAM free with both radios up. 5 GHz throughput is roughly 350 Mbit with both cores
saturated — mainline ath11k has no NSS offload for IPQ5018 and there is no prospect of one.

Not done: LED-to-port mapping and which socket is WAN are taken from the reference fork and
the GPL sources but have **not** been physically confirmed.

---

## Before you use this

**The MAC address is hard-coded** in `ipq5018-mr80x-v2.dts`:

```dts
&gmac1 { local-mac-address = [08 8a f1 39 98 c0]; };   /* lan / label */
port@0 { local-mac-address = [08 8a f1 39 98 c1]; };   /* wan */
&gmac0 { local-mac-address = [08 8a f1 39 98 c4]; };   /* unused */
```

and the radios derive theirs from the label MAC (`+2` and `+3`) in the caldata hotplug script.

Your unit's real MAC lives in the `tp_data` UBI volume, file `default-mac`, as six raw bytes:

```sh
ubiattach -m 13
mount -t ubifs ubi1:tp_data /mnt -o ro
hexdump -C /mnt/default-mac
```

Replace the three values above with `<mac>`, `<mac>+1` and `<mac>+4`. Doing this properly at
runtime (reading `tp_data` from `02_network`, as the reference fork does) is the obvious next
improvement and is the main reason this is not upstream-ready.

`0:art` on this device contains **no** MAC — those bytes read `0xff`, and U-Boot says so itself
(`eth0 MAC Address from ART is not valid`). Do not wire `nvmem-cells` to it.

---

## Installation

Recovery is always available over TFTP because sysupgrade never touches `0:SBL1` or `0:APPSBL`,
so U-Boot survives whatever you do to the rootfs.

**1. Try it from RAM first.** Interrupt autoboot to get the `IPQ5018#` prompt:

```
setenv ipaddr 192.168.1.1
setenv serverip 192.168.1.10
tftpboot 0x44000000 openwrt-qualcommax-ipq50xx-mercusys_mr80x-v2-initramfs-uImage.itb
bootm 0x44000000
```

**2. Flash.** From the running initramfs:

```sh
sysupgrade -n /tmp/openwrt-...-squashfs-sysupgrade.bin
```

If `sysupgrade` fails at the ubus stage-2 handover, write the UBI volumes by hand — the tar
holds `kernel` and `root`:

```sh
ubiupdatevol /dev/ubi0_1 -s <size-of-root>   root
ubiupdatevol /dev/ubi0_0 -s <size-of-kernel> kernel
```

rootfs first, matching what `nand_upgrade_tar()` does. Read the volumes back and compare
checksums before rebooting.

Note `scp` does not work against dropbear (no sftp-server); pipe instead:
`cat file | ssh root@host 'cat > /tmp/file'`.

---

## The five things that actually cost time

These are the non-obvious ones. Each was verified on hardware.

### 1. NAND ECC strength is 4, not 8

```dts
nand-ecc-strength = <4>;
nand-ecc-step-size = <512>;
```

U-Boot prints it plainly: `Device Size:128 MiB, Page size:2048, Spare Size:64, ECC:4-bit`.

Decoding at `<8>` returns data that looks clean — stable across reads, no ECC errors logged —
but with silently flipped bits. Symptoms it caused: caldata read from `0:art` was corrupt so
the WiFi firmware asserted in `phyrf_bdf.c:605`; `mtdsplit: error occured while reading from
"rootfs"`; `UBI error: unable to read from mtd15`; and `tp_data` appearing as "both volume
tables are corrupted" when it was in fact perfectly intact.

**Get this right before writing anything to NAND.**

### 2. The switch reset is GPIO 26, and U-Boot hides the problem

```dts
switch1: ethernet-switch@1d {
	reset-gpios = <&tlmm 26 GPIO_ACTIVE_LOW>;
};
```

U-Boot only runs `rtk_switch_init` when it falls through to its prompt. On the plain autoboot
path into NAND it never touches the RTL8367S, so the chip stays in reset and MDIO reads return
`0xffff` forever: `unrecognized switch (id=0xffff, ver=0xffff)`.

Every TFTP test goes through the U-Boot prompt, which is why the switch works there and fails
only once you boot from flash — an easy trap to spend hours in.

Do not be misled by the OEM device tree's `//soc/mdio@90000 phy-reset-gpio = <0x06 0x27 0x00>`
(GPIO 39). That is the MDIO/PHY reset and belongs on the bus node; it is a different pin for a
different job.

### 3. The CPU link must be 1 Gbit SGMII, not 2.5 Gbit HSGMII

```dts
&gmac1   { phy-mode = "sgmii"; fixed-link { speed = <1000>; full-duplex; }; };
&uniphy0 { assigned-clock-rates = <UNIPHY_REFCLK_25MHZ>; };
port@6   { phy-mode = "sgmii"; fixed-link { speed = <1000>; full-duplex; }; };
```

U-Boot configures the switch for 2.5 Gbit (`Set RTL8367S SGMII 2.5Gbps`) and the OEM runs it
that way, but at 3.125 GBaud this board loses packets:

| | 2.5G HSGMII | 1G SGMII |
|---|---|---|
| ping 32 B, 50 packets | 6 % loss | 0 % |
| ping 1400 B DF, 50 packets | 4–13 % loss | 0 % |
| 20 × HTTP GET | 8–11 / 20 | 20 / 20 |

The loss is invisible in every counter — `/proc/net/dev` shows `errs 0 drop 0 fifo 0` on the
conduit — because frames mangled on the SerDes are discarded by the PCS layer before the MAC
ever sees a frame. 1 Gbit is ample; the radios do ~350 Mbit.

The switch port is **6** (`extints` in `rtl8365mb_main.c` lists port 6 as the SGMII/HSGMII
external interface for the RTL8367S), and the switch node needs a child
`mdio { compatible = "realtek,smi-mdio"; }` listing the internal PHYs plus `phy-handle` on each
user port — without it the driver finds the chip and then aborts with
`no MDIO bus node` / `-ENODEV`.

### 4. `DEVICE_DTS_CONFIG` must match the machid

```make
DEVICE_DTS_CONFIG := config@mp02.1
```

This board's machid is `0x8040000` = mp02.1. A manual `bootm` works with any name because
U-Boot falls back to the FIT's default configuration, so this looks cosmetic — but `bootipq`
selects by machid and otherwise prints `Config not available` and drops into the OEM's HTTP
recovery mode. The OEM FIT ships 24 configurations and does contain `config@mp02.1`.

### 5. No pinctrl on the UART, or you lose console input

```dts
&blsp1_uart1 {
	status = "okay";
	/* deliberately no pinctrl-0 */
};
```

Re-muxing gpio20/21 in Linux kills console RX. TX keeps working because `printk` busy-polls,
so the port looks healthy while not a single RX interrupt arrives. The mux *value* is not
wrong — `blsp0_uart0` is legal for both pins — it is the pin configuration Linux writes.
Inheriting U-Boot's setup works.

### Bonus: measuring from WSL will lie to you

Every network measurement taken from WSL in this port was misleading (SSH stalling at
"banner exchange", phantom large-packet loss) because WSL2 NATs through the Windows host.
Measure from the host. And on a flaky link a single successful probe proves nothing — the
packet loss above only became visible over 20–50 repetitions.

---

## Building

```sh
git clone https://github.com/openwrt/openwrt
cd openwrt && git checkout ce16dd8
# apply src/existing-files.diff, copy src/new/ over the tree
./scripts/feeds update -a && ./scripts/feeds install -a
make menuconfig      # Qualcomm Atheros IPQ50xx -> MERCUSYS MR80X v2
make -j$(nproc)
```

Packages beyond the defaults:

```
CONFIG_PACKAGE_kmod-dsa-rtl8365mb=y
CONFIG_PACKAGE_kmod-mdio-gpio=y
CONFIG_PACKAGE_ethtool=y
CONFIG_PACKAGE_luci=y
```

### Contents of `src/`

| Path | What it is |
|---|---|
| `existing-files.diff` | changes to files that already exist in the tree |
| `new/target/linux/qualcommax/dts/ipq5018-mr80x-v2.dts` | the board DTS |
| `new/target/linux/qualcommax/patches-6.12/0918-*.patch` | poll for the switch instead of failing the first MDIO read |
| `new/package/kernel/mac80211/patches/ath11k/911-*.patch` | smaller ath11k DMA rings for 256 MB |
| `new/package/firmware/ipq-wifi/files/board-*` | per-model board data, EU region |

The `ipq-wifi` Makefile change is a local workaround: upstream serves board data from the
`qca-wireless` git repo, so a device whose BDF is not yet there needs the files picked up from
the package directory. The clean path is to submit the board data upstream.

### About the ath11k ring sizes

`911-ath11k-reduce-dma-buffer-to-save-memeory.patch` ships here with

```
DP_TX_COMP_RING_SIZE 8192   DP_RXDMA_BUF_RING_SIZE 2048
DP_RXDMA_MON_STATUS_RING_SIZE 1024   monitor buf/dst 128
```

rather than the much tighter values usually seen with that patch. Memory turned out never to be
the constraint on this board (~50 MB free with both radios), and `DP_TX_COMP_RING_SIZE` also
caps `DP_TX_IDR_SIZE`, i.e. in-flight TX descriptors — the wrong knob to turn down on a
router. These larger values are **not** throughput-tested; treat them as a starting point.

---

## Credits

The reference fork by **yanko-yankulov** for this exact device got several things right that
took a long time to rediscover independently: the 12-cell `boot-args`, switch port 6, GPIO 26
as the switch reset, and omitting pinctrl on the UART. Where this port and that fork disagree,
the fork was usually right.
