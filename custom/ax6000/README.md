# 红米 AX6000：闭源 Wi-Fi + honk / Nikki

在 GitHub 的 **Actions → Redmi AX6000 honk firmware → Run workflow** 手动构建。
成功后下载 `ax6000-honk-<run-id>`，其中包含固件、同批次 APK/kmods 和 `ax6000-evidence/` 核验记录。

## 此固件适用的设备

只适用于红米 AX6000 的 **MTK U-Boot、110 MiB 单 UBI** 布局：UBI 起点 `0x600000`，长度 `0x6e00000`，保留 NMBM。不是小米 AX6000，也不是本上游另一种 ubootmod/stock 布局。

首版基线为 Linux 6.12.112、闭源 mt_wifi 7.6.7.3。生成 factory 和 sysupgrade 两种镜像；名称不能代替当前设备升级入口的核对。已知旧系统可能把传统 kernel/rootfs UBI 误分派到 FIT 升级函数，本项目不提供强制刷写命令。

## 预装功能

- honk v0.1.0-beta.5、LuCI 配置页和内嵌 Doona 管理界面。
- Nikki v1.26.2、服务包 2026.10.10-r1、mihomo v1.19.32。
- 内置 BTF、BPF/TCX/cgroup、netkit、veth、NFQUEUE；Nikki 所需 dummy/tun/socket/tproxy。
- 闭源无线管理、EQoS、TurboACC、UPnP、wrtbwmon、ksmbd、Argon，以及拨号、双栈、DNS、存储和诊断工具。

新配置的 LAN 地址为 **192.168.6.1**。不预置管理密码、Wi-Fi 密码、拨号账号、订阅或 SSH 身份。honk 首次启动默认关闭，Nikki 默认 `enabled=0`；用户配置由后续私有迁移处理，不放进公共固件。

使用 honk 前先停止 Nikki，配置节点、规则和接口，再启用 honk；回到 Nikki 前先停止 honk。honk 的原生界面启用后位于 `http://192.168.6.1:9527/`，首次访问建立管理员账号；不开放 WAN 管理入口。Fake-IP、MRS 和已有 mihomo 策略组不能直接视为已迁移。

## 重现与后续补包

`versions.env`、`feeds.lock` 固定源代码；`wifi.config` 保留上游 MT7986 AX6000 无线参数，`config.seed` 只选择本设备和所需功能。工作流复用官方 honk/Nikki 打包脚本，通过本次 OpenWrt 工具链构建。

完整产物同时保留匹配的 APK/kmods。补装内核模块时使用**该构建的包**，不要因为官方源内核号也相同就混用，也不要强制忽略 kernel 依赖。`ax6000-evidence/firmware-audit.json` 记录实际 ABI、BTF、分区、包版本和大小。

Actions artifacts 保留 30 天，请下载归档。每次更新在新提交修改锁定版本后重新构建，不依赖浮动 feeds 自动升级。

## 验证范围

工作流检查最终镜像内的 BTF、分区、包与模块、二进制架构和首次启动默认值。通过代表离线构建候选合格；实际刷写、无线性能、HNAT/eBPF 共存和私人配置恢复需要在实机阶段验收。
