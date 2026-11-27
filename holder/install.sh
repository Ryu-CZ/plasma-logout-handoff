#!/usr/bin/env bash
# Install the logout holder from this bundle directory, or undo it with --restore.
#   sudo bash install.sh            install
#   sudo bash install.sh --restore  remove everything it installed
# If the login screen ever fails to appear: press Ctrl+Alt+F3, sign in,
# run the --restore line printed at the end, then: sudo systemctl restart plasmalogin
set -euo pipefail

here=$(cd -- "$(dirname -- "$0")" && pwd)
lib=/usr/local/lib/logout-holder
manifest=$lib/MANIFEST
kwin_args='--no-lockscreen --no-global-shortcuts --no-kactivities --inputmethod plasma-keyboard --locale1'

die() { echo "ERROR: $*" >&2; exit 1; }

action=${1:-install}
[[ $action == install || $action == --restore ]] || die "usage: $0 [--restore]"
(( EUID == 0 )) || exec sudo /usr/bin/bash "$here/install.sh" "$action"

# Installed path -> mode. Directories created here are removed on restore if empty.
declare -A files=(
    [$lib/logout-holder]=755
    [$lib/greeter/kwin_wayland]=755
    [$lib/greeter/libkwin.so.6]=755
    [$lib/greeter/plasma-login-wallpaper]=755
    [$lib/greeter-start]=755
    [/usr/local/bin/startplasma-login-wayland]=755
    [$lib/PACKAGES]=644
    [$lib/wallpaper-fallback]=644
    [/etc/systemd/system/logout-holder.service]=644
    [/etc/xdg/plasma-workspace/shutdown/logout-holder]=755
    [/etc/polkit-1/rules.d/60-logout-holder.rules]=644
    [/etc/systemd/user/plasma-login-kwin_wayland.service.d/80-logout-holder.conf]=644
    [/etc/systemd/user/plasma-wallpaper.service.d/80-logout-holder.conf]=644
)
dirs=($lib/greeter $lib /etc/xdg/plasma-workspace/shutdown /etc/xdg/plasma-workspace
      /etc/systemd/user/plasma-login-kwin_wayland.service.d /etc/systemd/user/plasma-wallpaper.service.d)

if [[ $action == --restore ]]; then
    systemctl stop logout-holder.service 2>/dev/null || true
    [[ -f $manifest ]] || die "$manifest not found; nothing recorded to remove."
    kept=0
    while read -r sum path; do
        [[ -e $path ]] || continue
        if [[ $(sha256sum <"$path" | cut -d' ' -f1) == "$sum" ]]; then
            rm -- "$path"
        else
            echo "Changed since install, left in place: $path" >&2
            kept=1
        fi
    done <"$manifest"
    rm -- "$manifest"
    # The helper (or sync-greeter-outputs.sh) copies the desktop's display
    # settings to the login screen at logout; put back what it had before.
    outputs=/var/lib/plasmalogin/.config/kwinoutputconfig.json
    rm -f -- "$outputs.logout-holder-new"
    if [[ -f $outputs.before-logout-holder ]]; then
        mv -f -- "$outputs.before-logout-holder" "$outputs"
        echo "Restored the login screen's previous display settings."
    elif [[ -f $outputs.none-before-logout-holder ]]; then
        rm -f -- "$outputs" "$outputs.none-before-logout-holder"
        echo "Removed the login screen's display settings (it had none before)."
    fi
    for d in "${dirs[@]}"; do rmdir -- "$d" 2>/dev/null || true; done
    systemctl daemon-reload
    (( kept == 0 )) || die 'Some files were left in place; see above.'
    echo 'Removed. The next logout and login screen behave as before.'
    exit 0
fi

for path in "${!files[@]}" "$manifest"; do
    [[ ! -e $path && ! -L $path ]] || die "$path already exists. Nothing changed."
done
for name in logout-holder logout-holder.service logout-holder-hook 60-logout-holder.rules greeter-start login-screen-start PACKAGES \
        greeter/kwin_wayland greeter/libkwin.so.6 greeter/plasma-login-wallpaper; do
    [[ -f $here/$name ]] || die "Bundle file $name missing. Nothing changed."
done
version=$(/usr/bin/kwin_wayland --version 2>/dev/null || true)
[[ $version == 'kwin 6.8.3' ]] || die "KWin is '$version'; the login screen compositor was built for 6.8.3. Nothing changed."
# Skipped where pacman does not track it (the test VM unpacks packages directly).
# The exact packages matter: distributions backport fixes (e.g. KDE bug 528936,
# lid closed -> prompt on the dark built-in screen) that the copy must carry
# too, and the copies use private Qt and KWin interfaces. greeter-start falls
# back to the stock programs once any of them changes.
packages=
if pacman -Q kwin >/dev/null 2>&1; then
    while read -r package; do
        [[ -z $package || -d /var/lib/pacman/local/$package ]] ||
            die "The bundle was built for $package, which is not installed. Nothing changed."
    done <"$here/PACKAGES"
    packages=$(<"$here/PACKAGES")
fi
if version=$(pacman -Q plasma-login-manager 2>/dev/null); then
    [[ $version == 'plasma-login-manager 6.8.3-'* ]] ||
        die "$version; the wallpaper program was built for 6.8.3. Nothing changed."
fi
[[ ! -e /etc/systemd/user/plasma-login-kwin_wayland.service.d ]] ||
    die 'The login screen compositor already has local overrides. Nothing changed.'
stock=$(sed -n 's/^ExecStart=//p' /usr/lib/systemd/user/plasma-login-kwin_wayland.service | tail -n1)
[[ $stock == "/usr/bin/kwin_wayland $kwin_args" ]] ||
    die "Unexpected login screen compositor command: $stock. Nothing changed."
# What runs as the wallpaper program without us (a theme may override it).
shopt -s nullglob
wallpaper_stock=$(sed -n 's/^ExecStart=//p' /usr/lib/systemd/user/plasma-wallpaper.service \
    /etc/systemd/user/plasma-wallpaper.service.d/*.conf | sed '/^$/d' | tail -n1)
shopt -u nullglob
[[ $wallpaper_stock =~ ^/[^[:space:]]+$ && -x $wallpaper_stock ]] ||
    die "Unexpected login screen wallpaper command: $wallpaper_stock. Nothing changed."
image=$(sed -n 's|^Image=file://||p' /etc/plasmalogin.conf | tail -n1)
[[ -n $image && -f $image ]] || die "No login screen wallpaper image found in /etc/plasmalogin.conf. Nothing changed."

# login-screen-start runs the packaged program and works only if the login
# manager finds /usr/local/bin first.
[[ -x /usr/bin/startplasma-login-wayland ]] || die '/usr/bin/startplasma-login-wayland not found. Nothing changed.'
pid=$(systemctl show plasmalogin.service -p MainPID --value)
if (( pid > 0 )); then
    environment=$(tr '\0' '\n' <"/proc/$pid/environ")
    search=:$(sed -n 's/^PATH=//p' <<<"$environment"):
    [[ ${search%%:/usr/bin:*}: == *:/usr/local/bin:* ]] ||
        die "The login manager does not search /usr/local/bin before /usr/bin ($search). Nothing changed."
    ! grep -q '^PLASMALOGIN_GREETER_EXEC=' <<<"$environment" ||
        die 'The login manager has its own login screen command (PLASMALOGIN_GREETER_EXEC). Nothing changed.'
fi
umask 022
put() { install -D -m "${files[$2]}" -- "$1" "$2"; }
# Until everything is in place, any failure removes what was installed.
trap 'for p in "${!files[@]}"; do rm -f -- "$p"; done; for d in "${dirs[@]}"; do rmdir -- "$d" 2>/dev/null || true; done; echo "Install failed; removed again." >&2' EXIT
put "$here/logout-holder" $lib/logout-holder
put "$here/greeter/kwin_wayland" $lib/greeter/kwin_wayland
put "$here/greeter/libkwin.so.6" $lib/greeter/libkwin.so.6
put "$here/greeter/plasma-login-wallpaper" $lib/greeter/plasma-login-wallpaper
put "$here/greeter-start" $lib/greeter-start
put "$here/login-screen-start" /usr/local/bin/startplasma-login-wayland
# Empty where pacman does not track packages (the test VM): no fallback check.
printf '%s\n' "$packages" >$lib/PACKAGES; chmod 644 $lib/PACKAGES
printf '%s\n' "$wallpaper_stock" >$lib/wallpaper-fallback; chmod 644 $lib/wallpaper-fallback
put "$here/logout-holder.service" /etc/systemd/system/logout-holder.service
put "$here/logout-holder-hook" /etc/xdg/plasma-workspace/shutdown/logout-holder
put "$here/60-logout-holder.rules" /etc/polkit-1/rules.d/60-logout-holder.rules
# No cap_sys_nice (real-time priority) on this copy, unlike the stock one: a
# file capability makes the loader ignore LD_LIBRARY_PATH, so the stock libkwin
# without the backdrop would load.
install -d -m755 /etc/systemd/user/plasma-login-kwin_wayland.service.d /etc/systemd/user/plasma-wallpaper.service.d
printf '%s\n' '# Installed by logout-holder: login screen compositor that shows the' \
    '# login wallpaper underneath until the wallpaper window has drawn.' '[Service]' 'ExecStart=' \
    "ExecStart=$lib/greeter-start kwin $kwin_args" \
    "Environment=\"KWIN_LOGIN_VM_WALLPAPER=$image\"" \
    >/etc/systemd/user/plasma-login-kwin_wayland.service.d/80-logout-holder.conf
printf '%s\n' '# Installed by logout-holder: wallpaper window that stays transparent' \
    '# until the picture has loaded, instead of black.' '[Service]' 'ExecStart=' \
    "ExecStart=$lib/greeter-start wallpaper" \
    >/etc/systemd/user/plasma-wallpaper.service.d/80-logout-holder.conf
systemctl daemon-reload
for path in "${!files[@]}"; do sha256sum -- "$path"; done |
    awk '{print $1, $2}' >"$manifest.new"
mv -T -- "$manifest.new" "$manifest"
trap - EXIT

echo "Installed. Login screen wallpaper: $image"
echo 'Takes effect at the next logout. Undo with:'
echo "  sudo bash $here/install.sh --restore"
