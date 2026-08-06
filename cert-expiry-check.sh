#!/bin/bash
# Crucible: Pandora Toolbox Enhancement (v2.0) — TLS certificate expiry check
#
# Warns when the server certificate is within WARN_DAYS of expiring. Safe to
# run manually or from cron (weekly is plenty). Works on macOS and RHEL8.
#
# Exit codes:
#   0 = certificate valid beyond the warning window (or no cert → HTTP-only)
#   1 = expiring within WARN_DAYS, already expired, or unreadable
#
# Env overrides:
#   CERT_FILE=/path/server.crt   (default: ./certs/server.crt next to this script)
#   WARN_DAYS=30                 (warn when fewer than this many days remain)

set -u
cd "$(dirname "$0")"

CERT_FILE="${CERT_FILE:-certs/server.crt}"
WARN_DAYS="${WARN_DAYS:-30}"

if [ ! -f "$CERT_FILE" ]; then
    echo "cert-expiry: no certificate at '$CERT_FILE' — HTTP-only deployment, nothing to check."
    exit 0
fi

end_date=$(openssl x509 -enddate -noout -in "$CERT_FILE" 2>/dev/null | cut -d= -f2)
if [ -z "$end_date" ]; then
    echo "cert-expiry: ✗ could not read certificate '$CERT_FILE'."
    exit 1
fi

# Best-effort days-remaining: GNU date first, then BSD/macOS date; tolerate failure.
now_epoch=$(date +%s)
end_epoch=$(date -d "$end_date" +%s 2>/dev/null \
    || date -j -f "%b %e %T %Y %Z" "$end_date" +%s 2>/dev/null \
    || echo "")
if [ -n "$end_epoch" ]; then
    left_msg="$(( (end_epoch - now_epoch) / 86400 )) day(s) left"
else
    left_msg="expires $end_date"
fi

warn_secs=$(( WARN_DAYS * 86400 ))
if ! openssl x509 -checkend 0 -noout -in "$CERT_FILE" >/dev/null 2>&1; then
    echo "cert-expiry: ✗ '$CERT_FILE' has ALREADY EXPIRED ($end_date). Rotate it now — DEPLOYMENT.md → Rotating the certificate."
    exit 1
elif ! openssl x509 -checkend "$warn_secs" -noout -in "$CERT_FILE" >/dev/null 2>&1; then
    echo "cert-expiry: ⚠ '$CERT_FILE' expires soon (${left_msg}, < ${WARN_DAYS} days; $end_date). Plan rotation — DEPLOYMENT.md → Rotating the certificate."
    exit 1
else
    echo "cert-expiry: ✓ '$CERT_FILE' OK (${left_msg}; expires $end_date)."
    exit 0
fi
