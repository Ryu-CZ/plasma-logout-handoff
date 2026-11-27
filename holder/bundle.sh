#!/usr/bin/env bash
# Assemble an install bundle: bash bundle.sh NEW_DIR WALLPAPER_BINARY
#   WALLPAPER_BINARY: plasma-login-wallpaper built with
#   patches/plasma-login-manager-6.8.3-logout-vm-wallpaper.patch (on Vandal,
#   from the plasmalogin-theme sources).
#   The login screen compositor comes from the KWin 6.8.3 build with the
#   distribution's backports (patches/kwin-6.8.3-arch-backport-*.patch, as in
#   Arch kwin 6.8.3-3) plus patches/kwin-6.8.3-logout-vm-backdrop.patch.
#   PACKAGES lists, at their installed versions (pacman database names), the
#   packages whose private code the copies depend on: those the copies bind
#   private symbols from, plus KWin (its plugins load into the copy),
#   qt6-wayland (a plugin loaded at run time) and the login manager (whose
#   greeter talks to the wallpaper program). BUNDLE_PACKAGES overrides the list.
#   install.sh refuses other versions, and greeter-start falls back to the
#   stock programs once any of them changes.
set -euo pipefail
here=$(cd -- "$(dirname -- "$0")" && pwd)
out=${1:?new bundle directory}
wallpaper=${2:?patched plasma-login-wallpaper}
kwin=${KWIN_BUILD:-$HOME/.cache/plasma-logout-handoff/backdrop/build}/bin
[[ ! -e $out ]] || { echo "$out exists" >&2; exit 1; }
mkdir -p -- "$out/greeter"
cp -- "$here"/{install.sh,logout-holder,logout-holder.service,logout-holder-hook,60-logout-holder.rules,greeter-start,login-screen-start} "$out/"
cp -L -- "$kwin/kwin_wayland" "$kwin/libkwin.so.6" "$out/greeter/"
cp -L -- "$wallpaper" "$out/greeter/plasma-login-wallpaper"
if [[ -n ${BUNDLE_PACKAGES:-} ]]; then
    packages=$BUNDLE_PACKAGES
else
    # The dynamic loader reports which library supplies each symbol a copy uses.
    copies=$(realpath -- "$out/greeter")
    trace=$(mktemp -d)
    trap 'rm -rf -- "$trace"' EXIT
    LD_LIBRARY_PATH=$copies LD_DEBUG=bindings LD_DEBUG_OUTPUT=$trace/kwin \
        ldd -r "$copies/kwin_wayland" >/dev/null
    LD_DEBUG=bindings LD_DEBUG_OUTPUT=$trace/wallpaper \
        ldd -r "$copies/plasma-login-wallpaper" >/dev/null
    # Private: a *PRIVATE_API symbol version, or "Private"/"private" in the
    # symbol or library name; bindings from the copies to system libraries only.
    # "QtPrivate" is ignored: it names template helpers that any library using
    # the same Qt template happens to export.
    libraries=$(cat -- "$trace"/* |
        awk -v copies="$copies/" '
            $2 == "binding" && index($4, copies) == 1 && index($7, copies) != 1 {
                names = $0
                gsub(/QtPrivate/, "", names)
                if (/PRIVATE/ || names ~ /symbol `[^\047]*Private/ || $7 ~ /private/) print $7
            }' |
        sort -u)
    grep -q '/libQt6' <<<"$libraries" || { echo 'No private Qt bindings found; trace unusable.' >&2; exit 1; }
    owners=$(pacman -Qqo $libraries)
    packages=$(pacman -Q $(printf '%s\n' kwin qt6-wayland plasma-login-manager $owners | sort -u) | tr ' ' -)
fi
printf '%s\n' "$packages" >"$out/PACKAGES"
(cd -- "$out" && find . -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 sha256sum >SHA256SUMS)
echo "$out"
