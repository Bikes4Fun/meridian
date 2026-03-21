#!/bin/bash
# Build the Meridian iOS app and run it in a Mac window (Mac Catalyst).
# No Simulator needed – launches as a normal desktop app.
# Requires: Xcode (provides xcodebuild)
#
# Usage:  ./run_ios.sh

set -e
cd "$(dirname "$0")"

echo "Building Meridian for Mac Catalyst (native window)..."
xcodebuild -project Meridian.xcodeproj -scheme Meridian \
  -destination 'platform=macOS,variant=Mac Catalyst' \
  -derivedDataPath .build \
  build

APP_PATH=".build/Build/Products/Debug-maccatalyst/Meridian.app"
EXEC_PATH="$APP_PATH/Contents/MacOS/Meridian"
if [ -d "$APP_PATH" ]; then
  echo ""
  echo "Build succeeded. Launching Meridian..."
  xattr -cr "$APP_PATH"
  if [ -x "$EXEC_PATH" ]; then
    "$EXEC_PATH" &
  else
    open "$APP_PATH"
  fi
else
  echo "Build may have succeeded but app not found at $APP_PATH"
fi
