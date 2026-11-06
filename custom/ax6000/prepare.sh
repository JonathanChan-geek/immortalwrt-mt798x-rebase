#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
TOP="$PWD"
source custom/ax6000/versions.env

clone_fixed() {
    local url="$1" rev="$2" dest="$3"
    if [ -d "$dest/.git" ]; then
        [ "$(git -C "$dest" rev-parse HEAD)" = "$rev" ]
        return
    fi
    git init -q "$dest"
    git -C "$dest" remote add origin "$url"
    git -C "$dest" fetch --depth 1 origin "$rev"
    git -C "$dest" checkout -q --detach FETCH_HEAD
}

clone_fixed https://github.com/daeuniverse/openwrt-packages.git "$DAE_PACKAGES_REV" .custom-sources/dae-packages
mkdir -p .custom-sources/honk-feed
for package in honk luci-app-honk luci-lib-daeuniverse vmlinux-btf-builtin; do
    cp -a ".custom-sources/dae-packages/$package" .custom-sources/honk-feed/
done
clone_fixed https://github.com/daeuniverse/honk.git "$HONK_REV" .custom-sources/honk-feed/honk/src

cp custom/ax6000/feeds.lock feeds.conf
printf 'src-link honk_custom %s/.custom-sources/honk-feed\n' "$TOP" >> feeds.conf
./scripts/feeds update -a
./scripts/feeds install -a
./scripts/feeds install -f -p nikki nikki luci-app-nikki mihomo-meta
./scripts/feeds install -f -p honk_custom honk luci-app-honk luci-lib-daeuniverse vmlinux-btf-builtin

# Change only the fresh-config fallback. Existing restored network config wins.
python3 - <<'PY'
from pathlib import Path
p = Path("package/base-files/files/bin/config_generate")
text = p.read_text()
old = 'lan) ipad=${ipaddr:-"192.168.1.1"} ;;'
new = 'lan) ipad=${ipaddr:-"192.168.6.1"} ;;'
if old in text:
    assert text.count(old) == 1
    p.write_text(text.replace(old, new))
else:
    assert new in text, "upstream config_generate changed"
PY

cat custom/ax6000/wifi.config custom/ax6000/config.seed > .config
make defconfig
python3 custom/ax6000/verify.py config
mkdir -p bin/ax6000-evidence
cp .config bin/ax6000-evidence/build.config
cp custom/ax6000/{versions.env,feeds.lock,wifi.config,config.seed} bin/ax6000-evidence/
git rev-parse HEAD > bin/ax6000-evidence/source-revision.txt
./scripts/feeds list -s > bin/ax6000-evidence/feeds-resolved.txt
