#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
TOP="$PWD"
source custom/ax6000/versions.env

cp custom/ax6000/feeds.lock feeds.conf
./scripts/feeds update -a
test "$(git -C feeds/adzero rev-parse HEAD)" = "$ADZERO_REV"
test "$(git -C feeds/nikki rev-parse HEAD)" = "$NIKKI_REV"

# Package the deployed official release with matching APK metadata, instead of
# overlaying a different executable over the old 1.19.32 package.
cp custom/ax6000/mihomo-meta.Makefile feeds/nikki/mihomo-meta/Makefile
grep -qx "PKG_VERSION:=$MIHOMO_VERSION" feeds/nikki/mihomo-meta/Makefile
./scripts/feeds update -i nikki

# Keep the existing optional traffic monitor available but inactive by default.
python3 - <<'PY'
from pathlib import Path
p = Path("feeds/wrtbwmon/wrtbwmon/Makefile")
text = p.read_text()
old = "+iptables +@BUSYBOX_CONFIG_IP"
new = "+iptables-nft +ip6tables-nft +ip-full"
if old in text:
    assert text.count(old) == 1
    p.write_text(text.replace(old, new))
else:
    assert new in text, "upstream wrtbwmon dependencies changed"
p = Path("feeds/wrtbwmon/wrtbwmon/net/etc/config/wrtbwmon")
text = p.read_text()
old, new = "option enabled '1'", "option enabled '0'"
if old in text:
    assert text.count(old) == 1
    p.write_text(text.replace(old, new))
else:
    assert new in text, "upstream wrtbwmon defaults changed"
PY
./scripts/feeds update -i wrtbwmon
./scripts/feeds install -a
./scripts/feeds install -f -p nikki nikki luci-app-nikki mihomo-meta
./scripts/feeds install -f -p adzero luci-app-adzero

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
