#!/bin/bash
# Xcode build phase: copy the engine into the app, so it runs without the project folder.
#   Contents/Resources/Engine/python   the Python from mac/build/vendor/python (see vendor_python.sh)
#   Contents/Resources/Engine/engine   fm27_squad_report.py and assets/
# Runs before Xcode signs the app. Without a prepared Python it only warns: the app then needs a project folder.
set -euo pipefail
MAC="$SRCROOT"
ROOT="$(cd "$MAC/.." && pwd)"
DEST="$TARGET_BUILD_DIR/$UNLOCALIZED_RESOURCES_FOLDER_PATH/Engine"

if [ ! -x "$MAC/build/vendor/python/bin/python3" ]; then
  echo "warning: no bundled Python yet (run mac/vendor_python.sh): this build needs a project folder to run the engine"
  rm -rf "$DEST"
  exit 0
fi

mkdir -p "$DEST/engine"
rsync -a --delete "$MAC/build/vendor/python/" "$DEST/python/"
rsync -a --delete --exclude ".DS_Store" "$ROOT/assets/" "$DEST/engine/assets/"
cp "$ROOT/fm27_squad_report.py" "$DEST/engine/fm27_squad_report.py"
