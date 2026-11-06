#!/usr/bin/env python3
"""Check effective configuration, then inspect the actual produced sysupgrade."""
import json
import lzma
import re
import shutil
import struct
import subprocess
import sys
import tarfile
from pathlib import Path

TOP = Path(__file__).resolve().parents[2]
DEVICE = "xiaomi_redmi-router-ax6000-mtkuboot"
EVIDENCE = TOP / "bin/ax6000-evidence"


def config(path):
    return dict(re.findall(r"^(CONFIG_\S+)=(.*)$", path.read_text(), re.M))


def check_config():
    actual = config(TOP / ".config")
    required = config(TOP / "custom/ax6000/config.seed")
    missing = {k: (v, actual.get(k)) for k, v in required.items() if actual.get(k) != v}
    assert not missing, f"defconfig dropped/changed requested settings: {missing}"
    assert actual.get("CONFIG_KERNEL_DEBUG_INFO_REDUCED") != "y"
    assert actual.get("CONFIG_TARGET_MULTI_PROFILE") != "y"
    assert actual.get("CONFIG_MTK_MT_WIFI_DRIVER_VERSION_7673") == "y"
    for name in ("sqm-scripts", "luci-app-sqm", "kmod-sched-cake"):
        assert actual.get("CONFIG_PACKAGE_" + name) not in ("y", "m"), name
    targets = [k for k, v in actual.items() if k.startswith("CONFIG_TARGET_mediatek_filogic_DEVICE_") and v == "y"]
    assert targets == [f"CONFIG_TARGET_mediatek_filogic_DEVICE_{DEVICE}"], targets
    print(f"Effective build configuration: {len(required)} required settings present")


def fdt_nodes(blob):
    magic, size, offset, strings, _, _, _, _, strings_size, struct_size = struct.unpack_from(">10I", blob)
    assert magic == 0xD00DFEED and size <= len(blob), "Invalid FDT"
    end = offset + struct_size
    names = blob[strings:strings + strings_size]
    nodes, stack = {}, []
    while offset < end:
        token, = struct.unpack_from(">I", blob, offset)
        offset += 4
        if token == 1:
            zero = blob.index(b"\0", offset)
            stack.append(blob[offset:zero].decode())
            offset = (zero + 4) & ~3
            nodes["/" + "/".join(stack[1:])] = {}
        elif token == 2:
            stack.pop()
        elif token == 3:
            length, name_offset = struct.unpack_from(">II", blob, offset)
            offset += 8
            name = names[name_offset:names.index(b"\0", name_offset)].decode()
            nodes["/" + "/".join(stack[1:])][name] = blob[offset:offset + length]
            offset = (offset + length + 3) & ~3
        elif token == 4:
            continue
        elif token == 9:
            return nodes
        else:
            raise AssertionError(f"Invalid FDT token {token}")
    raise AssertionError("FDT end token missing")


def metadata(blob):
    tail = blob[-8192:].decode("utf-8", errors="replace")
    decoder = json.JSONDecoder()
    for match in re.finditer(r"\{", tail):
        try:
            value, _ = decoder.raw_decode(tail[match.start():])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict) and "supported_devices" in value:
            return value
    raise AssertionError("fwtool metadata missing")


def btf_offsets(blob):
    result = []
    for match in re.finditer(b"\x9f\xeb\x01\x00", blob):
        pos = match.start()
        if pos + 24 > len(blob):
            continue
        _, _, _, header, types, type_len, strings, string_len = struct.unpack_from("<HBB5I", blob, pos)
        if (header == 24 and type_len > 0 and string_len > 0
                and pos + header + max(types + type_len, strings + string_len) <= len(blob)
                and blob[pos + header + strings] == 0):
            result.append(pos)
    return result


def package_db(path):
    packages = {}
    for block in path.read_text().split("\n\n"):
        fields = dict(line.split(":", 1) for line in block.splitlines() if len(line) > 1 and line[1] == ":" and line[0] in "PVD")
        if "P" in fields:
            packages[fields["P"]] = fields
    return packages


def check_artifacts():
    check_config()
    target = TOP / "bin/targets/mediatek/filogic"
    images = list(target.glob(f"*-{DEVICE}-squashfs-sysupgrade.bin"))
    factories = list(target.glob(f"*-{DEVICE}-squashfs-factory.bin"))
    assert len(images) == len(factories) == 1, (images, factories)
    image, factory = images[0], factories[0]
    assert 0 < factory.stat().st_size <= 110 * 1024 * 1024
    info = metadata(image.read_bytes())
    assert info["supported_devices"] == [DEVICE.replace("xiaomi_", "xiaomi,", 1)], info
    with tarfile.open(image) as archive:
        kernels = [m for m in archive.getmembers() if m.name.endswith("/kernel")]
        roots = [m for m in archive.getmembers() if m.name.endswith("/root")]
        assert len(kernels) == len(roots) == 1
        fit = fdt_nodes(archive.extractfile(kernels[0]).read())
        root_data = archive.extractfile(roots[0]).read()
    kernels = [p for n, p in fit.items() if n.startswith("/images/") and p.get("type") == b"kernel\0"]
    dtbs = [p for n, p in fit.items() if n.startswith("/images/") and p.get("type") == b"flat_dt\0"]
    assert len(kernels) == len(dtbs) == 1
    assert kernels[0]["compression"] == b"lzma\0"
    linux = lzma.decompress(kernels[0]["data"])
    banner = re.search(rb"Linux version [^\0\n]+", linux).group().decode()
    assert "Linux version 6.12.112 " in banner, banner
    btf = btf_offsets(linux)
    assert btf, "Produced kernel has no embedded BTF"
    dtb = fdt_nodes(dtbs[0]["data"])
    ubi = [p for p in dtb.values() if p.get("label") == b"ubi\0"]
    assert len(ubi) == 1 and struct.unpack(">II", ubi[0]["reg"]) == (0x600000, 0x6E00000)
    assert any("mediatek,nmbm" in p for p in dtb.values()), "NMBM missing"

    kernel_paths = list((TOP / "build_dir").glob("target-*/linux-mediatek_filogic/linux-6.12.112/.config"))
    assert len(kernel_paths) == 1, kernel_paths
    kconf = config(kernel_paths[0])
    core = "BPF BPF_SYSCALL BPF_JIT CGROUPS CGROUP_BPF NET_SCHED NET_CLS_ACT NET_XGRESS NET_NS NETKIT DEBUG_INFO_BTF FORTIFY_SOURCE".split()
    assert all(kconf.get("CONFIG_" + name) == "y" for name in core), {name: kconf.get("CONFIG_" + name) for name in core}
    for name in "VETH NFT_QUEUE NETFILTER_NETLINK_QUEUE NET_CLS_BPF NET_ACT_BPF TUN DUMMY".split():
        assert kconf.get("CONFIG_" + name) in ("y", "m"), name

    # Test the prepared source that produced this driver, not a patch file alone.
    drivers = list((TOP / "build_dir").glob("target-*/linux-mediatek_filogic/mt_wifi"))
    assert len(drivers) == 1, drivers
    query_test = json.loads(subprocess.check_output(
        [sys.executable, str(TOP / "custom/ax6000/test-wnm-query.py"), str(drivers[0])], text=True))

    work = TOP / ".custom-audit"
    work.mkdir(exist_ok=False)
    (work / "root.squashfs").write_bytes(root_data)
    root = work / "rootfs"
    # No device nodes are needed; avoid creating /dev/console on the build host.
    subprocess.run(["unsquashfs", "-no-progress", "-d", str(root), str(work / "root.squashfs"), "etc", "usr", "lib", "bin", "sbin"], check=True)
    packages = package_db(root / "lib/apk/db/installed")
    wanted = re.findall(r"^CONFIG_PACKAGE_([a-z][\w+-]*)=y$", (TOP / "custom/ax6000/config.seed").read_text(), re.M)
    absent = sorted(set(wanted) - packages.keys())
    assert not absent, f"Missing installed packages: {absent}"
    assert not {"sqm-scripts", "luci-app-sqm", "kmod-sched-cake"} & packages.keys()
    kernel = packages["kernel"]["V"]
    for name, package in packages.items():
        if name.startswith("kmod-"):
            assert f"kernel={kernel}" in package.get("D", "").split(), (name, package)
    assert packages["kmod-mt_wifi"]["V"].startswith("6.12.112.7.6.7.3"), packages["kmod-mt_wifi"]
    assert packages["kmod-mt_wifi"]["V"].endswith("-r2"), "Missing BTM query driver revision"
    assert packages["mihomo-meta"]["V"].startswith("1.19.32")
    assert packages["honk"]["V"].startswith("0.1.0_beta5")
    for path in ("usr/bin/honk-core", "usr/libexec/mihomo", "usr/bin/iperf3", "usr/libexec/bpftool-minimal"):
        binary = (root / path).read_bytes()
        assert binary[:6] == b"\x7fELF\x02\x01" and struct.unpack_from("<H", binary, 18)[0] == 183, path
    honk = (root / "usr/bin/honk-core").read_bytes()
    assert b"v0.1.0-beta.5" in honk and b"index.html" in honk
    assert re.search(r"option\s+'?enabled'?\s+'?0'?", (root / "etc/config/nikki").read_text())
    assert re.search(r"option\s+'?enabled'?\s+'?0'?", (root / "etc/config/wrtbwmon").read_text())
    assert "/etc/init.d/honk disable" in (root / "etc/uci-defaults/90-honk-autostart").read_text()
    assert "192.168.6.1" in (root / "bin/config_generate").read_text()
    root_shadow = next(line for line in (root / "etc/shadow").read_text().splitlines() if line.startswith("root:"))
    assert root_shadow.split(":")[1] in ("", "!", "*"), "Image contains a preset root password"
    assert not (root / "etc/dropbear/authorized_keys").exists(), "Private SSH identity must not be preinstalled"
    module_names = {p.name for p in (root / "lib/modules").rglob("*.ko")}
    builtin = "\n".join(p.read_text() for p in (root / "lib/modules").rglob("modules.builtin"))
    for name in "veth cls_bpf act_bpf nft_queue nfnetlink_queue dummy tun mt_wifi".split():
        assert name + ".ko" in module_names or "/" + name + ".ko" in builtin, name

    report = {"metadata": info, "kernel_banner": banner, "kernel_package": kernel,
              "btf_offsets_in_image": btf, "ubi_offset": "0x600000", "ubi_bytes": 110 * 1024 * 1024,
              "factory_bytes": factory.stat().st_size, "sysupgrade_bytes": image.stat().st_size,
              "packages": {name: p["V"] for name, p in sorted(packages.items())},
              "wnm_query_regression": query_test,
              "runtime_validation": "not flashed; offline checks only"}
    EVIDENCE.mkdir(exist_ok=True, parents=True)
    (EVIDENCE / "firmware-audit.json").write_text(json.dumps(report, indent=2) + "\n")
    shutil.copy2(kernel_paths[0], EVIDENCE / "kernel.config")
    (EVIDENCE / "board.dtb").write_bytes(dtbs[0]["data"])
    (EVIDENCE / "module-inventory.txt").write_text("\n".join(sorted(module_names)) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k != "packages"}, indent=2))
    print(f"Verified {len(packages)} installed packages and {len(module_names)} modules")
    assert work.resolve() == TOP / ".custom-audit"
    shutil.rmtree(work)


if __name__ == "__main__":
    if sys.argv[1:] == ["config"]:
        check_config()
    elif sys.argv[1:] == ["artifacts"]:
        check_artifacts()
    else:
        raise SystemExit("usage: verify.py config|artifacts")
