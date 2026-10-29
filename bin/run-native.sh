#!/bin/sh
# Fallback: run Brain Intake directly on the Mac, without Docker, on http://127.0.0.1:8765.
# Use it when Docker is unavailable. Stop the container first (bin/brain-intake down): both use port 8765.
# Pass --open to open the page. Uses the same vault (BRAIN_VAULT, default /opt/brain) and the same state folder.
REPO=$(cd "$(dirname "$0")/.." && pwd) || exit 1
export BRAIN_VAULT="${BRAIN_VAULT:-/opt/brain}" BRAIN_STATE="${BRAIN_STATE:-$REPO/state}"
for c in "${BRAIN_PYTHON:-}" /Library/Frameworks/Python.framework/Versions/Current/bin/python3 \
         /opt/homebrew/bin/python3 /usr/local/bin/python3 python3; do
  [ -n "$c" ] || continue
  if "$c" -c 'import yaml, requests, fitz, docx, pptx, openpyxl, numpy' >/dev/null 2>&1; then
    exec "$c" "$REPO/app/server.py" "$@"
  fi
done
echo "No python3 with PyYAML, requests, PyMuPDF, python-docx, python-pptx, openpyxl and numpy was found." >&2
echo "Set BRAIN_PYTHON to one that has them." >&2
exit 1
