# 红米 AX6000：Nikki 单核心 + AdZero

在 GitHub Actions 选择 **Redmi AX6000 Nikki and AdZero firmware** 手动构建。下载 `ax6000-nikki-adzero-<run-id>`，其中有 factory/sysupgrade、同批次 APK/kmods、独立 ImageBuilder 和 `ax6000-evidence/`。

分支构建命令：`gh workflow run ax6000-honk.yml --ref codex/ax6000-nikki-adzero`。文件名沿用已注册的旧工作流入口，避免为构建更改仓库默认分支；实际执行本分支的新配置，不包含 honk。

## 设备和基础

只适用于红米 AX6000 的 **MTK U-Boot、110 MiB 单 UBI** 布局，UBI 起点 `0x600000`、长度 `0x6e00000`、保留 NMBM。不是小米 AX6000，也不是另一种 stock/ubootmod 布局。保留 Linux 6.12.112、闭源 mt_wifi 7.6.7.3 及现有无线编译配置，不提供强刷命令。

mt_wifi r2 修复 BTM query 零长尾数组引起的 FORTIFY 告警，保留14字节头与内核保护；云端对实际准备的驱动源码运行14个边界/错误/正常用例。mtwifi-cfg-ucode r2 补齐 wireless-tools/iwpriv 依赖。兼容修复不等于已证明无线吞吐提升。

## 预装功能

- Nikki 1.26.2、服务 2026.10.10-r1；唯一 Mihomo v1.19.33 with_gvisor。设备专用 APK 使用官方 ARM64 二进制，固定发布摘要作下载校验，元数据与实际核心一致。定义见 `mihomo-meta.Makefile`。
- AdZero 0.23.10、adblock-fast 1.2.4-r4，依赖由本固件一起构建。**保护和自动分流默认关闭**，不预置严格/增强 DNS。固件不含 honk、其专用 UI/标记包和独立 home-access。
- 闭源无线、EQoS、TurboACC、UPnP、wrtbwmon、ksmbd、Argon、拨号/双栈/存储工具和原有按需诊断模块。BTF、iperf3、bpftool-minimal 保留，不自启测速。

不加 SQM/CAKE 或固定带宽限制。wrtbwmon 固定 LuCI 2.0.13/后端 1.2.1-r3、默认关闭，使用 iptables-nft/ip6tables-nft，不把它的统计当作 HNAT 全流量证明。

公共底包 LAN 为 **192.168.6.1**，不含密码、订阅、Wi-Fi/PPPoE 凭据或 SSH 身份；Nikki 默认 `enabled=0`。私人版从当前单核心现网配置组装，启用 Nikki 并保留原回家、手机订阅、选组和面板，不复用旧 honk overlay。

## AdZero 怎么接入

LuCI → 服务 → AdZero。日后开启保护前，先确认当前 Nikki 模式可用；建议一份 HaGeZi Light 主列表，不叠加大列表。官方适配通过 `mixin.yaml`/`nikki-rules` 添加域名 provider、DNS NXDOMAIN 策略及 Fake-IP 排除，保留原完整路由规则。core_only、禁用但非空的混入、Fake-IP whitelist 等会拒绝自动接入，不能强开绕过。

保护开启后有同步、DNS handoff 和 tcpdump/ucode 观察进程；规则内容变化可能重启 Nikki，内容未变不会重复重载。它是广告管理能力，不是提速插件。原配置已有的广告规则不会随 AdZero 关闭而消失。自动分流/严格 DNS/增强入口本构建不启用。

## 固定构建与私人打包

`versions.env`、`feeds.lock` 固定源；`wifi.config`/`config.seed` 定义设备与能力。仅复用下载和编译缓存，不复用旧固件。匹配内核模块必须使用这次构建的 APK，不强制忽略 kernel ABI 依赖。

在 Linux/WSL 解开本次 ImageBuilder，用 `make image PROFILE=xiaomi_redmi-router-ax6000-mtkuboot FILES=/absolute/private-overlay PACKAGES="... -dnsmasq"` 重组；完整包清单取本次 `ax6000-evidence/firmware-audit.json`。WSL 使用命令级 `env PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin`，避免带空格 Windows PATH 干扰。私人输入与输出只留本地，不能放进公共仓库或 Actions。

不要直接复制整个旧系统。保留新包程序，对照当前网络/无线格式；不复制活跃 cache.db、旧包数据库或旧核心。私人重组核验完整 kernel FIT、全包版本、文件权限、订阅可读权限与首启服务。Actions 产物保留30天，应下载归档。

## 验收

`verify.py config` 拒绝漏包和被禁止包；`verify.py artifacts` 读取实际镜像的 kernel/BTF/分区/包/模块/ELF，使用 QEMU 运行 ARM64 Mihomo `-v`，确认 AdZero 默认关闭及 honk 文件不存在。`verify-imagebuilder.py` 实际注入无秘密标记并检查包集合与内核不变。命令通过 pipefail 传递失败，上传不能掩盖失败。

离线通过表示构建候选合格。刷机、客户端过滤、Wi-Fi 稳定性、HNAT 吞吐和手机公网回家属于后续实机验收，不能用构建绿色状态代替。
