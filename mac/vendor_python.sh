#!/bin/bash
# Prepare the Python that ships inside the Mac app, in mac/build/vendor/python (gitignored).
# build.sh runs this by itself when that folder is missing; run it by hand to rebuild it.
#
# Python: a relocatable python-build-standalone CPython 3.13 (the kind uv installs), copied from
#   $PYTHON_STANDALONE, or else the newest ~/.local/share/uv/python/cpython-3.13.*-macos-aarch64-none.
# Packages: fmsave, copied from the project's .venv (pure Python), and backports-zstd (fmsave needs it before
#   Python 3.14), from the wheel in mac/build/vendor/wheels. Nothing is downloaded here.
set -euo pipefail
cd "$(dirname "$0")"
ROOT="$(cd .. && pwd)"
OUT=build/vendor/python

SRC="${PYTHON_STANDALONE:-}"
if [ -z "$SRC" ]; then
  SRC=$(ls -d "$HOME"/.local/share/uv/python/cpython-3.13.*-macos-aarch64-none 2>/dev/null | sort -V | tail -1 || true)
fi
[ -x "$SRC/bin/python3" ] || { echo "No standalone Python 3.13 found. Set PYTHON_STANDALONE to one."; exit 1; }

FMSAVE_SP=$(ls -d "$ROOT"/.venv/lib/python3.*/site-packages 2>/dev/null | tail -1 || true)
[ -d "$FMSAVE_SP/fmsave" ] || { echo "fmsave isn't in $ROOT/.venv: run Run Squad Report.command once first."; exit 1; }
ZSTD=$(ls build/vendor/wheels/backports_zstd-*-cp313-*macosx*arm64.whl 2>/dev/null | tail -1 || true)
[ -f "$ZSTD" ] || { echo "The backports-zstd wheel for cp313 arm64 isn't in mac/build/vendor/wheels."; exit 1; }

echo "Python from $SRC"
rm -rf "$OUT"
mkdir -p "$(dirname "$OUT")"
cp -R "$SRC" "$OUT"

# trim what the engine never uses: Tk, IDLE, headers, scripts, the installer for pip
LIB="$OUT/lib/python3.13"
rm -rf "$OUT/include" "$OUT/share" "$OUT/lib/pkgconfig" "$OUT"/lib/tcl* "$OUT"/lib/tk* "$OUT"/lib/itcl* "$OUT"/lib/thread* \
       "$LIB/idlelib" "$LIB/tkinter" "$LIB/turtledemo" "$LIB/ensurepip" "$LIB/EXTERNALLY-MANAGED"
find "$OUT/bin" -type f -o -type l | grep -Ev '/python3(\.13)?$' | xargs rm -f

SP="$LIB/site-packages"
cp -R "$FMSAVE_SP/fmsave" "$SP/"
cp -R "$FMSAVE_SP"/fmsave-*.dist-info "$SP/"
unzip -q -o "$ZSTD" -d "$SP"

# compile now, so the app never writes .pyc files into its own (signed) bundle
"$OUT/bin/python3" -m compileall -q -j 0 "$LIB" >/dev/null || true
find "$OUT" -name "*.opt-*.pyc" -delete

"$OUT/bin/python3" -c "import fmsave, sys; print('OK: Python', sys.version.split()[0], '· fmsave', __import__('importlib.metadata').metadata.version('fmsave'))"
du -sh "$OUT"
