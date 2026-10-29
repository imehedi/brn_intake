#!/bin/sh
# Start Brain Intake on http://127.0.0.1:8765. Pass --open to open it in the browser.
cd "$(dirname "$0")" || exit 1
for c in "$BRAIN_PYTHON" /Library/Frameworks/Python.framework/Versions/Current/bin/python3 \
         /opt/homebrew/bin/python3 /usr/local/bin/python3 python3; do
  [ -n "$c" ] || continue
  if "$c" -c 'import yaml, requests, fitz, docx, pptx, openpyxl, numpy' >/dev/null 2>&1; then
    exec "$c" server.py "$@"
  fi
done
echo "No python3 with PyYAML, requests, PyMuPDF, python-docx, python-pptx, openpyxl and numpy was found." >&2
echo "Set BRAIN_PYTHON to one that has them." >&2
exit 1
