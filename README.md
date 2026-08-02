# OpenWrt for the Mercusys MR3000X (sold/branded MR80X v2)

Working OpenWrt port for a Qualcomm IPQ5018 based Mercusys router, built against OpenWrt main
(`ce16dd8`). Everything below was verified on real hardware, with **kernel 6.18.39** as well as
6.12.100.

> **Read "Before you flash this" first.** The MAC address is currently hard-coded in the DTS
> for one specific unit. You will want to change that.

> **Kernel 6.18 needs a fix that is not upstream yet.** 6.18 added OTP support for this flash
> chip, and that support leaves the chip stuck in OTP mode, where the whole flash reads as
> `0xff` and every write fails. It looks exactly like a destroyed device but nothing is damaged.
> [Details below.](#kernel-618-and-the-otp-trap) The images here contain the fix. Do not run a
> stock 6.18 build on this router.

## Download

Prebuilt, tested images are on the [releases page](../../releases).

| File | Purpose |
|---|---|
| `openwrt-6.18-mercusys_mr80x-v2-initramfs-uImage.itb` | boot over TFTP from U-Boot, runs in RAM, does not touch the flash |
| `openwrt-6.18-mercusys_mr80x-v2-squashfs-sysupgrade.bin` | permanent install |

## Source

The complete tree is a branch on a fork of the official OpenWrt repository:

**https://github.com/Gameplayer-1-8/openwrt/tree/mercusys-mr80x-v2-6.18**

Four commits on top of `ce16dd8`: the switch detection retry, the SPI NAND OTP fix, the ath11k
ring sizes, and the device support itself. The `src/` directory in this repository is the older
patch-set form of the same changes, kept for reference.

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
| CPU to switch | SGMII **1 Gbit** on switch port 6 |
| Serial | 115200 8N1, `blsp1_uart1` @ 0x78af000 |

The unit's own `product-info` in the `tp_data` partition reads `product_name:MR3000X`,
`hw_ver:00000002`, `special_id:45550000` (EU). The EU board-data files for MR80X and MR3000X
are byte-identical, so the naming ambiguity does not matter in practice.

## Status

Working: both radios, DSA switch with `wan`/`lan1`/`lan2`/`lan3`, LuCI, sysupgrade, boot from
NAND, serial console (in and out), per-unit WiFi calibration read from flash at runtime.

About 50 MB RAM free with both radios up. 5 GHz throughput is roughly 350 Mbit with both cores
saturated, since mainline ath11k has no NSS offload for IPQ5018.

Ports and LEDs are confirmed on hardware:

| DSA port | Socket | LED | GPIO |
|---|---|---|---|
| `port@0` | WAN | `green:wan` | 10 |
| `port@1` | LAN1 | `green:lan-1` | 33 |
| `port@2` | LAN2 | `green:lan-2` | 11 |
| `port@3` | LAN3 | `green:lan-3` | 32 |
| `port@6` | CPU, SGMII 1 Gbit | | |

Plus a two-colour status LED on GPIO 13 (green) and GPIO 12 (orange), wired to
`led-running`/`led-upgrade` and `led-boot`/`led-failsafe` respectively.

The GPIO order matches `ALL_LED=10,33,11,32,13,12` from the MR3000Xv2 product configuration in
the GPL sources, which reads as wan, lan1, lan2, lan3, status green, status orange.

---

## Before you flash this

**The MAC address is hard-coded** in `ipq5018-mr80x-v2.dts`:

```dts
&gmac1 { local-mac-address = [08 8a f1 39 98 c0]; };   /* lan / label */
port@0 { local-mac-address = [08 8a f1 39 98 c1]; };   /* wan */
&gmac0 { local-mac-address = [08 8a f1 39 98 c4]; };   /* unused */
```

and the radios derive theirs from the label MAC (`+2` and `+3`) in the caldata hotplug script.
If you flash the prebuilt image unchanged, your router will use my unit's MAC addresses.

Your own MAC lives in the `tp_data` UBI volume, file `default-mac`, as six raw bytes. Once
OpenWrt is running you can read it with:

```sh
ubiattach -m 13
mount -t ubifs ubi1:tp_data /mnt -o ro
hexdump -C /mnt/default-mac
```

Then put `<mac>`, `<mac>+1` and `<mac>+4` into the three lines above and rebuild. Reading it at
runtime instead, from `02_network` as the reference fork does, is the obvious next improvement
and the main reason this is not upstream-ready.

`0:art` on this device contains **no** MAC. Those bytes read `0xff`, and U-Boot says so itself:
`eth0 MAC Address from ART is not valid`. Do not wire `nvmem-cells` to it.

---

## Installation

Nothing here is a one-way door. `sysupgrade` never touches `0:SBL1` or `0:APPSBL`, so U-Boot
always survives and you can TFTP a working image back at any time.

### What you need

* A USB-to-UART adapter, **3.3 V TTL**. Not RS-232, and never 5 V. See the warning in step 1,
  a 5 V adapter will destroy the SoC.
* An Ethernet cable between your PC and one of the router's LAN sockets.
* A TFTP server on your PC. On Windows, tftpd64 is the usual choice.
* Terminal software: PuTTY or TeraTerm on Windows, `screen` or `picocom` on Linux.

### 1. Serial console

> ### The adapter must be 3.3 V
>
> **A 5 V adapter will destroy the SoC.** The IPQ5018 UART pins are 3.3 V only and are not
> 5 V tolerant. There is no protection on these pads and the damage is immediate and permanent.
>
> Many cheap USB-to-serial adapters ship with a jumper or a solder bridge for 3.3 V / 5 V.
> Check it before you connect anything, and measure the TX pin against GND with a multimeter
> if you are not certain. It must read about 3.3 V, not 5 V.
>
> FTDI, CP2102 and CH340 boards are all available in 3.3 V versions. Avoid anything sold as an
> "RS-232 cable", that runs at plus/minus 12 V and is a different thing entirely.

The UART header sits at the front right of the PCB when you look at the board from the rear,
that is from the side the LAN sockets are on. The pads are labelled **RX**, **TX** and **GND**
on the silkscreen, so no probing is needed.

Connect those three and nothing else. Leave any VCC pad unconnected, the board powers itself.
The labels are from the board's point of view, so the connection is crossed:

```
adapter TX  ->  board RX
adapter RX  ->  board TX
adapter GND ->  board GND
```

If you get no output at all, swapping TX and RX is the first thing to try. It cannot damage
anything.

Port settings:

```
115200 baud, 8 data bits, no parity, 1 stop bit, no flow control
```

In PuTTY: connection type **Serial**, serial line `COMx`, speed `115200`, and under
*Connection > Serial* set flow control to **None**. On Linux, `screen /dev/ttyUSB0 115200`.

You should see U-Boot output as soon as you power the router on.

### 2. Give your PC a static IP

The router uses `192.168.1.1` in U-Boot, so put your PC on `192.168.1.10`.

**Windows:** *Settings > Network & Internet > Ethernet > Edit IP assignment > Manual*, switch
IPv4 on, then:

```
IP address       192.168.1.10
Subnet mask      255.255.255.0
Gateway          leave empty
```

The older route works too: *Control Panel > Network Connections*, right-click the adapter,
*Properties > Internet Protocol Version 4 > Properties*.

**Linux:**

```sh
sudo ip addr add 192.168.1.10/24 dev eth0
sudo ip link set eth0 up
```

Set the adapter back to DHCP when you are done.

### 3. Set up tftpd64

Download it from <https://pjo2.github.io/tftpd64/>, unpack it and run `tftpd64.exe`. No
installation needed.

1. Put both images from `images/` into one folder.
2. **Current Directory:** browse to that folder.
3. **Server interfaces:** select `192.168.1.10`. If several are offered, pick exactly this one,
   otherwise the router will not reach the server.
4. Switch to the **Tftp Server** tab and leave the window open while you work.

If the transfer later times out, the Windows firewall is the usual reason. Allow `tftpd64.exe`
for private networks, or switch the firewall off for the duration.

On Linux any TFTP daemon will do, for example:

```sh
sudo dnsmasq --enable-tftp --tftp-root=/path/to/images --port=0 -i eth0 -d
```

### 4. Boot the initramfs image over TFTP

This runs entirely from RAM and writes nothing to flash. A power cycle gets you back to
whatever was there before, so it is a safe way to try the port first.

Power on the router and **press a key immediately** in the serial terminal. The autoboot delay
is only one second. You are aiming for the `IPQ5018#` prompt.

```
setenv ipaddr 192.168.1.1
setenv serverip 192.168.1.10
tftpboot 0x44000000 openwrt-qualcommax-ipq50xx-mercusys_mr80x-v2-initramfs-uImage.itb
bootm 0x44000000
```

Two notes:

* `0x44000000` is a safe load address. The kernel unpacks to `0x41000000` and needs about
  22 MB, and the Q6 WiFi carveout starts at `0x4b000000`, so the image sits clear of both.
* On my unit `0:APPSBLENV` has a bad CRC, so U-Boot falls back to its built-in environment on
  every boot and the two `setenv` lines have to be repeated each time. `saveenv` makes them
  stick if you want that.

Interrupting autoboot has a side effect worth knowing about: U-Boot only initialises the
RTL8367S switch when it falls through to its prompt. That is why TFTP booting works even on
builds where booting from NAND leaves the switch dead. See finding 2 below.

The router comes up on `192.168.1.1`, with LuCI on port 80 and SSH open with no root password.

### 5. Flash it

`scp` does **not** work against dropbear, there is no sftp-server. Pipe the file instead:

```sh
cat openwrt-qualcommax-ipq50xx-mercusys_mr80x-v2-squashfs-sysupgrade.bin \
    | ssh root@192.168.1.1 'cat > /tmp/sysupgrade.bin'

ssh root@192.168.1.1 'sysupgrade -n /tmp/sysupgrade.bin'
```

Or upload the same file through LuCI under *System > Backup / Flash Firmware*, with "Keep
settings" unchecked.

Watch the serial console while it writes. The router reboots on its own and should come back on
`192.168.1.1`, this time from flash.

#### If sysupgrade fails at the ubus stage

You may see `Command failed: ubus call system sysupgrade ... (Connection failed)`. If that
happens, write the two UBI volumes by hand. The sysupgrade file is a tar containing `kernel`
and `root`:

```sh
tar xf sysupgrade.bin
cd sysupgrade-mercusys_mr80x-v2
ubinfo -a | grep -B2 -A2 Name          # find which volume is which

ubiupdatevol /dev/ubi0_1 -s $(stat -c%s root)   root      # rootfs first
ubiupdatevol /dev/ubi0_0 -s $(stat -c%s kernel) kernel
```

rootfs first, matching what `nand_upgrade_tar()` does. Read the volumes back and compare
checksums before you reboot:

```sh
dd if=/dev/ubi0_0 bs=4096 count=$(( ($(stat -c%s kernel) + 4095) / 4096 )) 2>/dev/null \
   | head -c $(stat -c%s kernel) | md5sum
md5sum kernel
```

### 6. First steps on the flashed router

The flashed system has a persistent SSH host key, unlike the initramfs which generates a
throwaway one on every boot. Your client will refuse to connect until you drop the old entry:

```sh
ssh-keygen -R 192.168.1.1
ssh root@192.168.1.1
```

Then set a password and switch the radios on, since OpenWrt ships them disabled:

```sh
passwd
uci set wireless.default_radio0.disabled='0'
uci set wireless.default_radio1.disabled='0'
uci commit wireless
wifi
```

Finally, put your PC's network adapter back to DHCP.

### Recovery

If the router does not come back after flashing, nothing is lost. `0:SBL1` and `0:APPSBL` are
never written, so U-Boot is intact. Power cycle, interrupt autoboot, and TFTP the initramfs
image again exactly as in step 4. From there you can rewrite the flash.

The OEM firmware in `rootfs_1` is left untouched by all of this as well.

---

## The six things that actually cost time

These are the non-obvious ones. Each was verified on hardware.

### 1. NAND ECC strength is 4, not 8

```dts
nand-ecc-strength = <4>;
nand-ecc-step-size = <512>;
```

U-Boot prints it plainly: `Device Size:128 MiB, Page size:2048, Spare Size:64, ECC:4-bit`.

Decoding at `<8>` returns data that looks clean, stable across reads and with no ECC errors
logged, but with silently flipped bits. Symptoms it caused: caldata read from `0:art` was
corrupt so the WiFi firmware asserted in `phyrf_bdf.c:605`; `mtdsplit: error occured while
reading from "rootfs"`; `UBI error: unable to read from mtd15`; and `tp_data` reporting "both
volume tables are corrupted" when the volume was in fact perfectly intact.

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
only once you boot from flash. That is an easy trap to spend hours in.

Do not be misled by the OEM device tree's `//soc/mdio@90000 phy-reset-gpio = <0x06 0x27 0x00>`
(GPIO 39). That is the MDIO/PHY reset and belongs on the bus node. It is a different pin for a
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
| ping 1400 B DF, 50 packets | 4 to 13 % loss | 0 % |
| 20 x HTTP GET | 8 to 11 of 20 | 20 of 20 |

The loss is invisible in every counter. `/proc/net/dev` shows `errs 0 drop 0 fifo 0` on the
conduit, because frames mangled on the SerDes are discarded by the PCS layer before the MAC
ever sees a frame. 1 Gbit is ample, the radios do about 350 Mbit.

The switch port is **6** (`extints` in `rtl8365mb_main.c` lists port 6 as the SGMII/HSGMII
external interface for the RTL8367S), and the switch node needs a child
`mdio { compatible = "realtek,smi-mdio"; }` listing the internal PHYs plus `phy-handle` on each
user port. Without it the driver finds the chip and then aborts with `no MDIO bus node` and
`-ENODEV`.

### 4. `DEVICE_DTS_CONFIG` must match the machid

```make
DEVICE_DTS_CONFIG := config@mp02.1
```

This board's machid is `0x8040000`, which is mp02.1. A manual `bootm` works with any name
because U-Boot falls back to the FIT's default configuration, so this looks cosmetic. But
`bootipq` selects by machid and otherwise prints `Config not available` and drops into the
OEM's HTTP recovery mode. The OEM FIT ships 24 configurations and does contain `config@mp02.1`.

### 5. No pinctrl on the UART, or you lose console input

```dts
&blsp1_uart1 {
	status = "okay";
	/* deliberately no pinctrl-0 */
};
```

Re-muxing gpio20/21 in Linux kills console RX. TX keeps working because `printk` busy-polls, so
the port looks healthy while not a single RX interrupt arrives. The mux *value* is not wrong,
`blsp0_uart0` is legal for both pins. It is the pin configuration Linux writes. Inheriting
U-Boot's setup works.

### Kernel 6.18 and the OTP trap

By far the most expensive one, and the reason this section is no longer called "five".

Kernel 6.18 added OTP support for the ESMT F50L1G41LB and F50D1G41LB. Declaring the OTP layouts
makes MTD registration create `user-otp` and `factory-otp` nvmem devices, and the OTP access that
follows leaves `CFG_OTP_ENABLE` set on the chip while the driver's `cfg_cache` says it is clear.
`spinand_set_cfg()` returns early whenever the cache already matches, so every later attempt to
leave OTP mode is silently a no-op. No warning is printed.

The chip then serves its OTP area instead of the array:

| Page | Content |
|---|---|
| 0 | unique ID page, a 32 byte pattern repeated 16 times |
| 1 | ONFI parameter page (`ONFI` ... `POWERCHIP PSR1GS20DX`, ESMT rebadges this die) |
| 2 and up | unwritten OTP, so `0xff` |

Reads report success, because the hardware erased-page detector correctly flags those pages as
blank. Writes fail with `-EIO`. A `sysupgrade` erases the rootfs, cannot write it back, and
U-Boot then says `Both image corrupted`. Everything points at a destroyed flash. It is not:
the content is untouched the whole time.

What the diagnosis looked like on hardware, with a debug print of the config register:

```
cfg as found at probe = 00 (otp_en=0)   first probe, chip is clean
cfg as found at probe = 40 (otp_en=1)   second probe, OTP was left on
OTP off: cached=00 chip=40 -> chip=00   the cache and the chip disagree
```

Forcing that one register write brought everything back instantly. `0:appsbl` went from all
`0xff` to `7f 45 4c 46`, `rootfs` to `55 42 49 23`, and `0:art` matched its earlier checksum
byte for byte.

The fix, `0402-mtd-spinand-esmt-do-not-register-OTP-areas.patch`, drops the OTP declarations for
both ESMT entries. 6.12 never had OTP support for these parts, which is why it is unaffected.

Two things made this findable after a lot of fruitless source comparison. A raw read through the
`MEMREAD` ioctl with `MTD_OPS_RAW` bypasses both the ECC engine and the erased-page detector and
shows what the chip really puts on the wire; `tools/mtdprobe.c` does that, and pre-fills its
buffers with `0xa5` so "the driver wrote `0xff`" stays distinguishable from "the driver never
wrote anything". And simply looking at the bytes that did survive instead of only hashing them:
the `ONFI` signature identified the mode in seconds.

---

## Building

```sh
git clone -b mercusys-mr80x-v2-6.18 https://github.com/Gameplayer-1-8/openwrt
cd openwrt
./scripts/feeds update -a && ./scripts/feeds install -a
make menuconfig      # Qualcomm Atheros IPQ50xx -> MERCUSYS MR80X v2
                     # for 6.18: Advanced configuration -> Use the testing kernel
make -j$(nproc)
```

That branch already contains everything. The older route, applying `src/existing-files.diff` and
copying `src/new/` over a stock checkout of `ce16dd8`, still works and produces the same tree.

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
| `new/target/linux/qualcommax/patches-6.18/0402-*.patch` | keep the SPI NAND out of OTP mode on kernel 6.18 |
| `new/package/kernel/mac80211/patches/ath11k/911-*.patch` | smaller ath11k DMA rings for 256 MB |
| `new/package/firmware/ipq-wifi/files/board-*` | per-model board data, EU region |

The `ipq-wifi` Makefile change is a local workaround. Upstream serves board data from the
`qca-wireless` git repo, so a device whose BDF is not yet there needs the files picked up from
the package directory. The clean path is to submit the board data upstream.

### About the ath11k ring sizes

`911-ath11k-reduce-dma-buffer-to-save-memeory.patch` ships here with

```
DP_TX_COMP_RING_SIZE 8192   DP_RXDMA_BUF_RING_SIZE 2048
DP_RXDMA_MON_STATUS_RING_SIZE 1024   monitor buf/dst 128
```

rather than the much tighter values usually seen with that patch. Memory turned out never to be
the constraint on this board, with about 50 MB free and both radios up, and
`DP_TX_COMP_RING_SIZE` also caps `DP_TX_IDR_SIZE`, the number of in-flight TX descriptors. That
is the wrong knob to turn down on a router. These larger values are **not** throughput-tested,
so treat them as a starting point.

---

## Credits

The reference fork by **yanko-yankulov** for this exact device got several things right that
took a long time to rediscover independently: the 12-cell `boot-args`, switch port 6, GPIO 26
as the switch reset, and omitting pinctrl on the UART. Where this port and that fork disagree,
the fork was usually right.
