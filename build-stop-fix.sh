#!/usr/bin/env bash
# Build only the two starter binaries, in existing KDE 6.8.3 build trees.
set -euo pipefail
here=$(cd -- "$(dirname -- "$0")" && pwd)
desktop=$(realpath "${1:?desktop build directory}")
greeter=$(realpath "${2:?greeter build directory}")
output=$(realpath -m "${3:?new output directory}")
mkdir -- "$output"
build() (
    tree=$1
    file=$2
    target=$3
    source=$(grep '^CMAKE_HOME_DIRECTORY:INTERNAL=' "$tree/CMakeCache.txt")
    source=${source#*=}
    cd "$source"
    git diff --quiet HEAD -- "$file"
    patch="$here/patches/$target.patch"
    git apply --check "$patch"
    git apply "$patch"
    trap 'git apply -R "$patch"' EXIT
    cmake --build "$tree" --target "$target" --parallel 3
    install -m 755 "$tree/bin/$target" "$output/$target"
    # Use matching guest libraries, not RPATHs from the local build.
    if command -v patchelf >/dev/null; then
        patchelf --remove-rpath "$output/$target"
    fi
)
build "$desktop" startkde/startplasma.cpp startplasma-wayland
build "$greeter" src/frontend/startkde/startplasma.cpp startplasma-login-wayland
