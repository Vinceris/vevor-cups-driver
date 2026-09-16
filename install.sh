#!/bin/bash
#
# install.sh - install the open-source VEVOR label printer driver on macOS.
#
#   sudo ./install.sh              build (if needed), install filter + PPDs,
#                                  re-point every queue that still uses the
#                                  vendor driver to the new PPD
#   sudo ./install.sh --add NAME   also create a new queue NAME for the first
#                                  VEVOR printer found on USB (203 dpi PPD)
#   sudo ./install.sh --add NAME --300dpi   same, with the 300 dpi PPD
#
# Nothing here touches the vendor package; see uninstall-vendor.sh for that.
#
# Copyright 2026 Mattia Colombo - Apache-2.0

set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
FILTER_DIR=/Library/Printers/VevorOpen/Filter
PPD_DIR=/Library/Printers/PPDs/Contents/Resources
PPD203="$PPD_DIR/vevor-label-203dpi.ppd"
PPD300="$PPD_DIR/vevor-label-300dpi.ppd"

ADD_QUEUE=""
USE300=0
while [ $# -gt 0 ]; do
  case "$1" in
    --add) ADD_QUEUE="$2"; shift 2 ;;
    --300dpi) USE300=1; shift ;;
    -h|--help) sed -n '2,15p' "$0"; exit 0 ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
done

if [ "$(uname -s)" != "Darwin" ]; then
  echo "This installer is for macOS. On Linux: make && copy build/rastertovevor" >&2
  echo "to \$(cups-config --serverbin)/filter and install ppd/*.ppd with lpadmin." >&2
  exit 1
fi
if [ "$(id -u)" -ne 0 ]; then
  echo "Please run with sudo: sudo $0 $*" >&2
  exit 1
fi

# 1. build as the invoking user (keeps build/ owned by them)
if [ ! -x "$HERE/build/rastertovevor" ]; then
  echo "== building"
  if [ -n "${SUDO_USER:-}" ]; then
    sudo -u "$SUDO_USER" make -C "$HERE"
  else
    make -C "$HERE"
  fi
fi
lipo -archs "$HERE/build/rastertovevor" >/dev/null

# 2. install filter + PPDs
echo "== installing filter to $FILTER_DIR"
mkdir -p "$FILTER_DIR"
install -m 755 -o root -g wheel "$HERE/build/rastertovevor" "$FILTER_DIR/rastertovevor"
echo "== installing PPDs to $PPD_DIR"
mkdir -p "$PPD_DIR"
install -m 644 -o root -g admin "$HERE/ppd/vevor-label-203dpi.ppd" "$PPD203"
install -m 644 -o root -g admin "$HERE/ppd/vevor-label-300dpi.ppd" "$PPD300"

# 3. re-point queues that still use the vendor filter
echo "== checking existing queues"
for f in /etc/cups/ppd/*.ppd; do
  [ -f "$f" ] || continue
  q="$(basename "$f" .ppd)"
  if grep -q '/Library/Printers/VevorPrinter300/' "$f"; then
    echo "   $q -> vendor 300 dpi driver, switching to $PPD300"
    lpadmin -p "$q" -P "$PPD300" -E
  elif grep -q '/Library/Printers/VevorPrinter/' "$f"; then
    echo "   $q -> vendor 203 dpi driver, switching to $PPD203"
    lpadmin -p "$q" -P "$PPD203" -E
  elif grep -q '/Library/Printers/VevorOpen/' "$f"; then
    echo "   $q already uses this driver, refreshing PPD"
    if grep -q 'vevor-label-300dpi' "$f"; then lpadmin -p "$q" -P "$PPD300" -E
    else lpadmin -p "$q" -P "$PPD203" -E; fi
  fi
done

# 4. optionally add a new queue for the USB printer
if [ -n "$ADD_QUEUE" ]; then
  uri="$(lpinfo -v 2>/dev/null | awk '/usb:\/\/VEVOR/ {print $2; exit}')"
  if [ -z "$uri" ]; then
    echo "No VEVOR printer found on USB (lpinfo -v). Plug it in and retry, or run:" >&2
    echo "  lpadmin -p $ADD_QUEUE -E -v 'usb://VEVOR/Y486?serial=...' -P $PPD203" >&2
    exit 1
  fi
  ppd="$PPD203"; [ "$USE300" = 1 ] && ppd="$PPD300"
  echo "== adding queue $ADD_QUEUE at $uri"
  lpadmin -p "$ADD_QUEUE" -E -v "$uri" -P "$ppd" -L "VEVOR Label Printer" -o printer-is-shared=false
fi

echo
echo "Done. Queues now using this driver:"
grep -l '/Library/Printers/VevorOpen/' /etc/cups/ppd/*.ppd 2>/dev/null | sed 's#.*/##; s#\.ppd$##; s#^#   #' || echo "   (none yet - use --add NAME)"
echo
echo "Test print:  lp -d <queue> -o media=w283h425 some-label.pdf"
