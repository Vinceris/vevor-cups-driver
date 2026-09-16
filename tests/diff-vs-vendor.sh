#!/bin/sh
#
# diff-vs-vendor.sh - differential test against the original VEVOR filter.
#
# The vendor filter is x86_64-only, so this needs Rosetta 2
# (softwareupdate --install-rosetta --agree-to-license) and the vendor
# package still installed. Feeds the same synthetic rasters to both filters
# with the same PPD options and compares the output byte-for-byte.
#
# Usage: sh tests/diff-vs-vendor.sh      (after `make`)
#
# Copyright 2026 Mattia Colombo - Apache-2.0

set -e
HERE="$(cd "$(dirname "$0")/.." && pwd)"
VENDOR203=/Library/Printers/VevorPrinter/Filter/rastertolabel
VENDOR300=/Library/Printers/VevorPrinter300/Filter/rastertolabel
OURS="$HERE/build/rastertovevor"
MKRAS="$HERE/build/mkras"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

[ -x "$OURS" ] && [ -x "$MKRAS" ] || { echo "run make first"; exit 2; }
[ -x "$VENDOR203" ] || { echo "vendor filter not installed at $VENDOR203"; exit 2; }
arch -x86_64 /usr/bin/true 2>/dev/null || { echo "Rosetta 2 is not installed; cannot run the vendor filter"; exit 2; }

# The vendor filter refuses to run unless the queue's device URI contains
# //VEVOR and /Y486, so it needs a real queue name in argv and the queue's PPD.
QUEUE="${QUEUE:-VEVOR_Y486}"
VPPD203="/etc/cups/ppd/$QUEUE.ppd"
[ -f "$VPPD203" ] || { echo "queue $QUEUE not found (set QUEUE=name)"; exit 2; }

fail=0
run_case() {  # dpi w h pattern options
  dpi=$1; w=$2; h=$3; pat=$4; opts=$5
  vendor=$VENDOR203; [ "$dpi" = 300 ] && vendor=$VENDOR300
  "$MKRAS" "$w" "$h" "$dpi" "$pat" > "$TMP/in.ras"
  PPD="$VPPD203" PRINTER="$QUEUE" "$vendor" 1 u t 1 "$opts" "$TMP/in.ras" > "$TMP/vendor.out" 2>/dev/null || true
  PPD="$VPPD203" "$OURS" 1 u t 1 "$opts" "$TMP/in.ras" > "$TMP/ours.out" 2>/dev/null || true
  if cmp -s "$TMP/vendor.out" "$TMP/ours.out"; then
    echo "  ok   $dpi dpi ${w}x${h} $pat [$opts]"
  else
    echo "  DIFF $dpi dpi ${w}x${h} $pat [$opts]"; fail=1
    cmp "$TMP/vendor.out" "$TMP/ours.out" || true
  fi
}

run_case 203 12 8 toprow ""
run_case 203 798 1198 diag ""
run_case 203 4 2 corner "Rotate=1"
run_case 203 4 2 corner "Rotate=2"
run_case 203 4 2 corner "Rotate=3"
run_case 203 8 4 toprow "Darkness=Default zePrintRate=1 zeMediaTracking=BLine GapOrMarkHeight=5"
run_case 203 8 4 toprow "zeMediaTracking=Continuous AutoDotted=1 AdjustHoriaontal=-3 AdjustVertical=2"
[ -x "$VENDOR300" ] && run_case 300 1200 1800 diag ""

[ $fail = 0 ] && echo "IDENTICAL to the vendor filter" || { echo "differences found"; exit 1; }
