Board data for the Mercusys MR3000X / MR80X v2 (IPQ5018 + QCN6122).

Both files are the genuine per-model BDFs taken from the OEM firmware, EU region,
revision "default":

  board-mercusys_mr80x-v2.ipq5018   from /EU/MR80X/default/lib/firmware/IPQ5018/WIFI_FW/bdwlan.b24
  board-mercusys_mr80x-v2.qcn6122   from .../WIFI_FW/qcn6122/bdwlan.b60

How the variant was identified: the .bXX suffix is the board_id in hex, and the factory
caldata in 0:ART carries the same board_id at offset 0x3a - 0x24 for the IPQ5018 region at
0x1000, 0x60 for the QCN6122 region at 0x26800. Byte-similarity between the caldata and each
candidate BDF then pins down region and revision: EU/default matches 99.98 % and 99.95 %,
while revision 00000001 only reaches ~88 %.

The EU "default" files are byte-identical across MR80X, MR3000X, MR1800X and MR70X
(md5 bbcd52a165e477221404164eb3d82344 for IPQ5018, 503daccafc8e25573593f70b3297f2fc for
QCN6122), so the MR80X-vs-MR3000X naming ambiguity does not matter.

Packed into board-2.bin containers under the single name
  bus=ahb,qmi-chip-id=0,qmi-board-id=255,variant=MERCUSYS-MR80X-V2
which must match qcom,ath11k-calibration-variant in the DTS exactly - the lookup is a
case-sensitive strcmp and there is no generic fallback entry in these containers.

board_id 0xff / chip_id 0 in the boot log is normal for IPQ5018 on AHB; all upstream board
files use qmi-board-id=255.

Per-unit calibration is NOT in these files. It is extracted from 0:ART at runtime by
target/linux/qualcommax/ipq50xx/base-files/etc/hotplug.d/firmware/11-ath11k-caldata
(offsets 0x1000 and 0x26800, 0x20000 bytes each).
