#!/bin/bash
#
# uninstall.sh - remove the open-source driver (filter + PPDs). Queues that
# use it are left in place but will stop working; delete them with
# `lpadmin -x NAME` or re-point them to another PPD.
#
# Copyright 2026 Mattia Colombo - Apache-2.0

set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
  echo "Please run with sudo: sudo $0" >&2
  exit 1
fi

rm -rf /Library/Printers/VevorOpen
rm -f /Library/Printers/PPDs/Contents/Resources/vevor-label-203dpi.ppd \
      /Library/Printers/PPDs/Contents/Resources/vevor-label-300dpi.ppd
echo "Removed /Library/Printers/VevorOpen and the two PPDs."
grep -l '/Library/Printers/VevorOpen/' /etc/cups/ppd/*.ppd 2>/dev/null | sed 's#.*/##; s#\.ppd$##; s#^#queue still pointing here: #' || true
