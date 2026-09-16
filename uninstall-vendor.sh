#!/bin/bash
#
# uninstall-vendor.sh - remove the proprietary VEVOR macOS driver package
# (com.mygreatcompany.pkg.VevorPrinter 1.5.8): its x86_64-only CUPS filters,
# the two PPDs, the "LaunchVevor" auto-add helper and its LaunchDaemon that
# crash-loops every 10 s on Apple Silicon Macs without Rosetta.
#
#   sudo ./uninstall-vendor.sh            refuses if a queue still uses the
#                                         vendor driver (run install.sh first)
#   sudo ./uninstall-vendor.sh --force    remove anyway
#
# Files are moved to a backup folder, not deleted, so this is reversible.
#
# Copyright 2026 Mattia Colombo - Apache-2.0

set -euo pipefail

FORCE=0
[ "${1:-}" = "--force" ] && FORCE=1

if [ "$(id -u)" -ne 0 ]; then
  echo "Please run with sudo: sudo $0 $*" >&2
  exit 1
fi

BACKUP="/Library/Printers/VevorVendorBackup-$(date +%Y%m%d-%H%M%S)"
PKG=com.mygreatcompany.pkg.VevorPrinter

if [ "$FORCE" = 0 ]; then
  still="$(grep -l '/Library/Printers/VevorPrinter' /etc/cups/ppd/*.ppd 2>/dev/null | sed 's#.*/##; s#\.ppd$##' || true)"
  if [ -n "$still" ]; then
    echo "These queues still use the vendor driver:" >&2
    echo "$still" | sed 's/^/   /' >&2
    echo "Run 'sudo ./install.sh' first (it re-points them), or use --force." >&2
    exit 1
  fi
fi

mkdir -p "$BACKUP"
echo "== backup folder: $BACKUP"

if launchctl print system/com.launch.vevor >/dev/null 2>&1; then
  echo "== stopping LaunchDaemon com.launch.vevor"
  launchctl bootout system/com.launch.vevor || true
fi
if [ -f /Library/LaunchDaemons/com.launch.vevor.plist ]; then
  mv /Library/LaunchDaemons/com.launch.vevor.plist "$BACKUP/"
  echo "   moved com.launch.vevor.plist"
fi

for d in /Library/Printers/VevorPrinter /Library/Printers/VevorPrinter300; do
  if [ -d "$d" ]; then
    mv "$d" "$BACKUP/"
    echo "   moved $d"
  fi
done

for p in "/Library/Printers/PPDs/Contents/Resources/Vevor Label Printer.ppd.gz" \
         "/Library/Printers/PPDs/Contents/Resources/Vevor Label Printer 300.ppd.gz"; do
  if [ -f "$p" ]; then
    mv "$p" "$BACKUP/"
    echo "   moved $(basename "$p")"
  fi
done

if pkgutil --pkg-info "$PKG" >/dev/null 2>&1; then
  pkgutil --forget "$PKG" >/dev/null
  echo "   forgot package receipt $PKG"
fi

echo
echo "Vendor driver removed. To restore: move the contents of $BACKUP back and"
echo "run: sudo launchctl bootstrap system /Library/LaunchDaemons/com.launch.vevor.plist"
