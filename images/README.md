# Images

The images in this directory are the **kernel 6.12** build, kept because they were the first
ones verified on hardware and they are a safe fallback.

For the current **kernel 6.18** build, use the [releases page](../../../releases). Those carry
the SPI NAND OTP fix that 6.18 requires on this device, described in the main README under
"Kernel 6.18 and the OTP trap".

| File | Kernel | Purpose |
|---|---|---|
| `openwrt-qualcommax-ipq50xx-mercusys_mr80x-v2-initramfs-uImage.itb` | 6.12.100 | boot over TFTP, runs in RAM |
| `openwrt-qualcommax-ipq50xx-mercusys_mr80x-v2-squashfs-sysupgrade.bin` | 6.12.100 | permanent install |

Checksums are in `sha256sums.txt`.
