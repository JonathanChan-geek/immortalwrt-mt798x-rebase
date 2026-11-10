#!/usr/bin/env python3
"""Exercise FILES injection with a non-private marker, using only matching APKs."""
import importlib.util
import json
import subprocess
import tarfile
import tempfile
from pathlib import Path

TOP = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("firmware_verify", TOP / "custom/ax6000/verify.py")
verify = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verify)
target = TOP / "bin/targets/mediatek/filogic"
archives = list(target.glob("*imagebuilder*.tar.zst"))
assert len(archives) == 1, archives
audit = json.loads((verify.EVIDENCE / "firmware-audit.json").read_text())
original = next(target.glob(f"*-{verify.DEVICE}-squashfs-sysupgrade.bin"))


def kernel_payload(path):
    with tarfile.open(path) as archive:
        member = next(m for m in archive.getmembers() if m.name.endswith("/kernel"))
        nodes = verify.fdt_nodes(archive.extractfile(member).read())
    return next(p["data"] for p in nodes.values() if p.get("type") == b"kernel\0")


with tempfile.TemporaryDirectory(prefix="ax6000-repack-") as directory:
    work = Path(directory)
    subprocess.run(["tar", "--zstd", "-xf", str(archives[0]), "-C", str(work)], check=True)
    builders = [p for p in work.iterdir() if p.is_dir()]
    assert len(builders) == 1
    builder = builders[0]
    assert not (builder / "repositories").exists() or not (builder / "repositories").read_text().strip(), "ImageBuilder unexpectedly uses remote feeds"
    marker = "ax6000 offline repack check\n"
    overlay = work / "overlay"
    (overlay / "etc").mkdir(parents=True)
    (overlay / "etc/ax6000-repack-check").write_text(marker)
    packages = " ".join(audit["packages"]) + " -dnsmasq"
    subprocess.run(["make", "-C", str(builder), "image", f"PROFILE={verify.DEVICE}",
                    f"PACKAGES={packages}", f"FILES={overlay}", "DISABLED_SERVICES=adzero adzero-dns adblock-fast"], check=True)
    rebuilt = next((builder / "bin/targets/mediatek/filogic").glob(f"*-{verify.DEVICE}-squashfs-sysupgrade.bin"))
    assert kernel_payload(rebuilt) == kernel_payload(original), "Repacking changed the kernel payload"
    with tarfile.open(rebuilt) as archive:
        member = next(m for m in archive.getmembers() if m.name.endswith("/root"))
        squashfs = work / "repacked.squashfs"
        squashfs.write_bytes(archive.extractfile(member).read())
    def read_file(name):
        return subprocess.check_output(["unsquashfs", "-cat", str(squashfs), name]).decode()
    assert read_file("etc/ax6000-repack-check") == marker
    db = work / "installed"
    db.write_text(read_file("lib/apk/db/installed"))
    installed = {name: data["V"] for name, data in verify.package_db(db).items()}
    assert installed == audit["packages"], "Repacked package inventory differs from verified firmware"
    result = {"imagebuilder": archives[0].name, "private_data_used": False,
              "marker_injected": True, "kernel_payload_unchanged": True,
              "package_inventory_unchanged": True, "package_count": len(installed),
              "repacked_sysupgrade_bytes": rebuilt.stat().st_size}
    (verify.EVIDENCE / "imagebuilder-audit.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
