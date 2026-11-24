#!/bin/bash
# Build FM27 Companion for Mac and open it.
#   ./build.sh          build (Debug) and open
#   ./build.sh test     run the tests
#   ./build.sh release  build Release (left in mac/build/DerivedData.noindex/Build/Products/Release)
#   ./build.sh install  build Release, put it in /Applications and open it
# Builds live in a ".noindex" folder so Spotlight and Launchpad only ever show the copy in /Applications.
set -euo pipefail
cd "$(dirname "$0")"

if ! command -v xcodegen >/dev/null; then
  echo "XcodeGen is missing: brew install xcodegen"; exit 1
fi
xcodegen generate --quiet
# the Python that ships inside the app (once; delete mac/build/vendor/python to make it again)
[ -x build/vendor/python/bin/python3 ] || ./vendor_python.sh

DERIVED=build/DerivedData.noindex
RELEASE_APP="$DERIVED/Build/Products/Release/FM27 Companion.app"

release() {
    xcodebuild -project SquadReport.xcodeproj -scheme SquadReport -configuration Release \
      -derivedDataPath "$DERIVED" -quiet build
}

case "${1:-}" in
  test)
    xcodebuild -project SquadReport.xcodeproj -scheme SquadReport -destination 'platform=macOS' \
      -derivedDataPath "$DERIVED" -quiet test
    ;;
  release)
    release
    echo "Built mac/$RELEASE_APP"
    ;;
  install)
    release
    osascript -e 'quit app id "com.squadreport.mac"' 2>/dev/null || true
    sleep 2
    rm -rf "/Applications/Squad Report.app" "/Applications/FM27 Companion.app"
    cp -R "$RELEASE_APP" /Applications/
    open "/Applications/FM27 Companion.app"
    echo "Installed /Applications/FM27 Companion.app"
    ;;
  *)
    xcodebuild -project SquadReport.xcodeproj -scheme SquadReport -configuration Debug \
      -derivedDataPath "$DERIVED" -quiet build
    open "$DERIVED/Build/Products/Debug/FM27 Companion.app"
    ;;
esac
