#!/bin/bash
# Double-click me to start your FM27 squad report. Leave the window open, then just refresh
# http://localhost:8027 in your browser whenever you've saved in FM.
cd "$(dirname "$0")" || exit 1
echo ""
echo "  FM27 Squad Report"
echo "  -----------------"

PY=""
for c in python3.15 python3.14 python3.13 python3.12 python3 \
         /Library/Frameworks/Python.framework/Versions/3.15/bin/python3 \
         /Library/Frameworks/Python.framework/Versions/3.14/bin/python3 \
         /opt/homebrew/bin/python3 /usr/local/bin/python3; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)' 2>/dev/null; then
    PY="$c"; break
  fi
done
if [ -z "$PY" ]; then
  echo "  Couldn't find Python 3.12 or newer. Install it from python.org, then double-click this again."
  read -n 1 -s -r -p "  Press any key to close…"; exit 1
fi

if [ ! -x ".venv/bin/python" ]; then
  echo "  First run: setting things up (only happens once)…"
  if ! "$PY" -m venv .venv || ! .venv/bin/python -m pip install --quiet --disable-pip-version-check fmsave; then
    echo "  Setup failed. Check your internet connection and try again."
    rm -rf .venv
    read -n 1 -s -r -p "  Press any key to close…"; exit 1
  fi
else
  # keep the save reader current so FM27 patches keep working (skipped quietly if offline)
  .venv/bin/python -m pip install --quiet --disable-pip-version-check --upgrade --timeout 5 fmsave >/dev/null 2>&1 || true
fi

.venv/bin/python fm27_squad_report.py "$@"
echo ""
read -n 1 -s -r -p "  Press any key to close this window…"
echo ""
