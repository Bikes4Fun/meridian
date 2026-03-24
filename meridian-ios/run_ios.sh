#!/bin/bash
# Build the Meridian iOS app and run it in the iOS Simulator.
# Requires: Xcode (provides xcodebuild, simctl)
#
# Usage:  ./run_ios.sh
# Optional: SIM_DEVICE_NAME="iPhone SE (3rd generation)" ./run_ios.sh

set -e
cd "$(dirname "$0")"

SIM_NAME="${SIM_DEVICE_NAME:-iPhone 16}"

echo "Building Meridian for iOS Simulator ($SIM_NAME)..."
xcodebuild -project MeridianFamily.xcodeproj -scheme MeridianFamily \
  -destination "platform=iOS Simulator,name=${SIM_NAME}" \
  -derivedDataPath .build \
  build

APP_PATH="$(pwd)/.build/Build/Products/Debug-iphonesimulator/MeridianFamily.app"
BUNDLE_ID="com.meridian.MeridianFamily"

if [ ! -d "$APP_PATH" ]; then
  echo "Build may have succeeded but app not found at $APP_PATH"
  exit 1
fi

# Resolve a single simulator UDID (avoids ambiguous "multiple matching destinations")
SIM_UDID=$(xcrun simctl list devices available 2>/dev/null | grep "${SIM_NAME} (" | head -1 | sed -E 's/.*\(([A-F0-9-]+)\).*/\1/')
if [ -z "$SIM_UDID" ]; then
  echo "No available simulator named \"${SIM_NAME}\". List devices: xcrun simctl list devices available"
  exit 1
fi

echo ""
echo "Build succeeded. Opening Simulator (UDID ${SIM_UDID})..."
open -a Simulator
xcrun simctl boot "$SIM_UDID" 2>/dev/null || true
# Wait until the simulator OS has finished booting (reduces FBSOpenApplicationServiceErrorDomain 4)
xcrun simctl bootstatus "$SIM_UDID" -b 2>/dev/null || sleep 4
sleep 2

echo "Installing ${APP_PATH}..."
xcrun simctl uninstall "$SIM_UDID" "$BUNDLE_ID" 2>/dev/null || true
xcrun simctl install "$SIM_UDID" "$APP_PATH"

echo "Launching ${BUNDLE_ID}..."
if xcrun simctl launch "$SIM_UDID" "$BUNDLE_ID"; then
  echo "Done."
else
  echo ""
  echo "simctl launch failed (FBS code 4 often means the app quit immediately or the simulator was not ready)."
  echo "Try: open Simulator, wait until the home screen appears, then run this script again."
  echo "If it keeps failing, open Console.app and filter for MeridianFamily to see a crash log."
  exit 1
fi
