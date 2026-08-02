"""Identify the device model by comparing the factory ART caldata against
every candidate OEM BDF.

Rationale: at manufacture the FTM tool writes the model's BDF template into
the ART partition and fills in the per-unit calibration fields. So the ART
caldata should be byte-wise closest to the BDF of the *correct* model.
"""
import glob
import os

ROOT = "/tmp/rootfs_fixed"
FW = "lib/firmware/IPQ5018/WIFI_FW"


def load(path):
    with open(path, "rb") as f:
        return f.read()


def similarity(a, b):
    n = min(len(a), len(b))
    same = sum(1 for i in range(n) if a[i] == b[i])
    return same / n


def collect(sub):
    """Return {label: path} for every bdwlan candidate."""
    out = {}
    for region in ("EU", "US"):
        for model in sorted(os.listdir(os.path.join(ROOT, region))):
            mdir = os.path.join(ROOT, region, model)
            if not os.path.isdir(mdir):
                continue
            for rev in sorted(os.listdir(mdir)):
                pat = os.path.join(mdir, rev, FW, sub, "bdwlan.*")
                for p in sorted(glob.glob(pat)):
                    out[f"{region}/{model}/{rev}/{os.path.basename(p)}"] = p
    for p in sorted(glob.glob(os.path.join(ROOT, FW, sub, "bdwlan.*"))):
        out[f"GENERIC/{os.path.basename(p)}"] = p
    return out


for chip, sub, caldata_file in (
    ("IPQ5018 (2.4GHz)", "", "caldata_ipq5018_correct.bin"),
    ("QCN6122 (5GHz)", "qcn6122", "caldata_qcn6122_correct.bin"),
):
    cal = load(caldata_file)
    print(f"===== {chip}: factory caldata vs candidate BDFs =====")
    print(f"  caldata: {caldata_file} ({len(cal)} bytes)")
    cands = collect(sub)
    scored = []
    for label, path in cands.items():
        bdf = load(path)
        scored.append((similarity(cal, bdf), label, len(bdf)))
    scored.sort(reverse=True)
    for score, label, size in scored:
        print(f"    {score*100:6.2f}%  {label:<48s} ({size} bytes)")
    print()
    best = scored[0]
    runner = scored[1] if len(scored) > 1 else None
    print(f"  >>> best match: {best[1]}  ({best[0]*100:.2f}%)")
    if runner:
        print(f"      runner-up : {runner[1]}  ({runner[0]*100:.2f}%)")
        print(f"      margin    : {(best[0]-runner[0])*100:.2f} percentage points")
    print()
