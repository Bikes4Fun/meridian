#!/bin/bash
# Build the Meridian iOS app and run it in the iOS Simulator.
# Requires: Xcode (provides xcodebuild, simctl)
#
# Usage:  ./run_ios.sh

set -e
cd "$(dirname "$0")"

echo "Building Meridian for iOS Simulator..."
xcodebuild -project Meridian.xcodeproj -scheme Meridian \
  -destination 'platform=iOS Simulator,name=iPhone SE (3rd generation)' \
  -derivedDataPath .build \
  build

APP_PATH=".build/Build/Products/Debug-iphonesimulator/Meridian.app"
if [ -d "$APP_PATH" ]; then
  echo ""
  echo "Build succeeded. Launching Simulator and installing app..."
  xcrun simctl boot "iPhone SE (3rd generation)" 2>/dev/null || true
  xcrun simctl install booted "$APP_PATH"
  xcrun simctl launch booted com.meridian.Meridian
else
  echo "Build may have succeeded but app not found at $APP_PATH"
fi
