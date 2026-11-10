# AX6000 wrapper for the official, tested with_gvisor ARM64 release.
include $(TOPDIR)/rules.mk

PKG_NAME:=mihomo-meta
PKG_VERSION:=1.19.33
PKG_RELEASE:=1
PKG_SOURCE:=mihomo-linux-arm64-v$(PKG_VERSION).gz
PKG_SOURCE_URL:=https://github.com/MetaCubeX/mihomo/releases/download/v$(PKG_VERSION)
# Official release asset digest, required by OpenWrt download validation.
PKG_HASH:=ba408b317080ee265c46cb923a50018c1b82cbd708551cdd46a1e3e307396187
PKG_LICENSE:=GPL-3.0-or-later
PKG_MAINTAINER:=JonathanChan-geek

include $(INCLUDE_DIR)/package.mk

define Package/mihomo-meta
  SECTION:=net
  CATEGORY:=Network
  TITLE:=Mihomo official stable ARM64 core
  URL:=https://github.com/MetaCubeX/mihomo
  DEPENDS:=@TARGET_mediatek_filogic +ca-bundle +ip-full +kmod-inet-diag +kmod-tun
  PROVIDES:=mihomo
  CONFLICTS:=mihomo-alpha
  VARIANT:=meta
  DEFAULT_VARIANT:=1
  ALTERNATIVES:=300:/usr/bin/mihomo:/usr/libexec/mihomo
endef

define Build/Prepare
	$(INSTALL_DIR) $(PKG_BUILD_DIR)
	gzip -dc $(DL_DIR)/$(PKG_SOURCE) > $(PKG_BUILD_DIR)/mihomo
endef

define Build/Configure
endef

define Build/Compile
endef

define Package/mihomo-meta/install
	$(INSTALL_DIR) $(1)/usr/libexec
	$(INSTALL_BIN) $(PKG_BUILD_DIR)/mihomo $(1)/usr/libexec/mihomo
endef

$(eval $(call BuildPackage,mihomo-meta))
