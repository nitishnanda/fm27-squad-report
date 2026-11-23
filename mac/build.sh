#!/bin/bash
# Build Squad Report for Mac and open it.
#   ./build.sh          build (Debug) and open
#   ./build.sh test     run the tests
#   ./build.sh release  build Release into mac/build/Release/Squad Report.app
set -euo pipefail
cd "$(dirname "$0")"

if ! command -v xcodegen >/dev/null; then
  echo "XcodeGen is missing: brew install xcodegen"; exit 1
fi
xcodegen generate --quiet

case "${1:-}" in
  test)
    xcodebuild -project SquadReport.xcodeproj -scheme SquadReport -destination 'platform=macOS' \
      -derivedDataPath build/DerivedData -quiet test
    ;;
  release)
    xcodebuild -project SquadReport.xcodeproj -scheme SquadReport -configuration Release \
      -derivedDataPath build/DerivedData -quiet build
    mkdir -p build/Release
    rm -rf "build/Release/Squad Report.app"
    cp -R "build/DerivedData/Build/Products/Release/Squad Report.app" build/Release/
    echo "Built mac/build/Release/Squad Report.app"
    ;;
  *)
    xcodebuild -project SquadReport.xcodeproj -scheme SquadReport -configuration Debug \
      -derivedDataPath build/DerivedData -quiet build
    open "build/DerivedData/Build/Products/Debug/Squad Report.app"
    ;;
esac
