#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
SRC="$PWD/.custom-sources/honk-feed/honk/src"
export CARGO_HOME="${CARGO_HOME:-$HOME/.cargo}"
export PATH="$CARGO_HOME/bin:$PATH"
stable="$(sed -n 's/^channel = "\(.*\)"/\1/p' "$SRC/rust-toolchain.toml")"
nightly="$(sed -n 's/^channel = "\(.*\)"/\1/p' "$SRC/crates/honk-ebpf/rust-toolchain.toml")"
rustup toolchain install "$stable" --profile minimal --target aarch64-unknown-linux-musl
rustup toolchain install "$nightly" --profile minimal --component rust-src,llvm-tools
source "$SRC/.github/ci/pins.env"
archive="${RUNNER_TEMP:-/tmp}/ax6000-bpf-linker.tar.zst"
curl -fL --retry 3 -o "$archive" "https://github.com/aya-rs/bpf-linker/releases/download/v$BPF_LINKER_VERSION/bpf-linker-x86_64-unknown-linux-musl.tar.zst"
# The upstream pin is a release-download integrity requirement.
echo "$BPF_LINKER_SHA256  $archive" | sha256sum -c -
zstd -dc "$archive" | tar -xf - -C "$CARGO_HOME/bin"
bpf-linker --version
