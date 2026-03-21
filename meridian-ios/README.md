# Meridian iOS

Native Swift/UIKit app. Connects to the Meridian API (login, alert, check-in, chat).

## Build and run

**Option A – Command line + Xcode**

```bash
./run_ios.sh
```

Builds the app, then opens Xcode and Simulator. In Xcode, press **Cmd+R** to run.

**Option B – Xcode only**

```bash
open Meridian.xcodeproj
```

Choose an **iOS Simulator** (e.g. iPhone 16) as the run destination, then **Cmd+R**.

If the build fails with "no such module 'UIKit'", the destination is set to macOS. Switch to an iOS Simulator in the scheme selector next to the Run button.

## API URL

Default: `http://127.0.0.1:8000`. Override via `MERIDIAN_API_URL` in Info.plist (Xcode project) or bundle.
