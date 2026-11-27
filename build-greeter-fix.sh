#!/usr/bin/env bash
# Build only the patched login screen starter (startplasma-login-wayland):
#   bash build-greeter-fix.sh PLASMA_LOGIN_MANAGER_GIT NEW_OUTPUT_DIR
# PLASMA_LOGIN_MANAGER_GIT is only read: its v6.8.3 tag is cloned into the
# output directory, which also gets the unpatched build for comparison.
# NEW_OUTPUT_DIR/{stock,patched}/startplasma-login-wayland are the results.
set -euo pipefail
here=$(cd -- "$(dirname -- "$0")" && pwd)
upstream=$(realpath "${1:?plasma-login-manager git checkout}")
output=$(realpath -m "${2:?new output directory}")
mkdir -- "$output"
git clone --quiet --depth 1 --branch v6.8.3 "file://$upstream" "$output/src"
# The distribution's makepkg.conf flags, without -march=native. LTO and
# --as-needed keep the program's imports and libraries those of the package.
export CXXFLAGS='-O2 -fno-plt -fexceptions -Wp,-D_FORTIFY_SOURCE=3 -Wp,-D_GLIBCXX_ASSERTIONS -fstack-clash-protection -fcf-protection -flto=auto'
export LDFLAGS='-Wl,-O1 -Wl,--sort-common -Wl,--as-needed -Wl,-z,relro -Wl,-z,now -flto=auto'
cmake -S "$output/src" -B "$output/build" -G Ninja -DCMAKE_BUILD_TYPE=None \
    -DCMAKE_INSTALL_PREFIX=/usr -DCMAKE_INSTALL_LIBEXECDIR=lib -DBUILD_TESTING=OFF \
    -DCMAKE_SKIP_RPATH=ON >"$output/configure.log" 2>&1
build() {
    cmake --build "$output/build" --target startplasma-login-wayland --parallel 4 >"$output/build-$1.log" 2>&1
    install -D -s -m 755 "$output/build/bin/startplasma-login-wayland" "$output/$1/startplasma-login-wayland"
}
build stock
git -C "$output/src" apply "$here/patches/startplasma-login-wayland.patch"
build patched
sha256sum "$output"/{stock,patched}/startplasma-login-wayland
