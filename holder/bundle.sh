#!/usr/bin/env bash
# Assemble an install bundle: bash bundle.sh NEW_DIR WALLPAPER_BINARY
#   WALLPAPER_BINARY: plasma-login-wallpaper built with
#   patches/plasma-login-manager-6.8.3-logout-vm-wallpaper.patch (on Vandal,
#   from the plasmalogin-theme sources).
#   The login screen compositor comes from the KWin 6.8.3 build with the
#   distribution's backports (patches/kwin-6.8.3-arch-backport-*.patch, as in
#   Arch kwin 6.8.3-3) plus patches/kwin-6.8.3-logout-vm-backdrop.patch.
#   PACKAGES lists the installed packages the copies were built against
#   (pacman database names; default: this machine's, or BUNDLE_PACKAGES).
#   install.sh refuses other versions, and greeter-start falls back to the
#   stock programs once any of them changes.
set -euo pipefail
here=$(cd -- "$(dirname -- "$0")" && pwd)
out=${1:?new bundle directory}
wallpaper=${2:?patched plasma-login-wallpaper}
kwin=${KWIN_BUILD:-$HOME/.cache/plasma-logout-handoff/backdrop/build}/bin
packages=${BUNDLE_PACKAGES:-$(pacman -Q kwin qt6-base qt6-declarative qt6-wayland plasma-login-manager | tr ' ' -)}
[[ ! -e $out ]] || { echo "$out exists" >&2; exit 1; }
mkdir -p -- "$out/greeter"
cp -- "$here"/{install.sh,logout-holder,logout-holder.service,logout-holder-hook,60-logout-holder.rules,greeter-start,login-screen-start} "$out/"
cp -L -- "$kwin/kwin_wayland" "$kwin/libkwin.so.6" "$out/greeter/"
cp -L -- "$wallpaper" "$out/greeter/plasma-login-wallpaper"
printf '%s\n' "$packages" >"$out/PACKAGES"
(cd -- "$out" && find . -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 sha256sum >SHA256SUMS)
echo "$out"
