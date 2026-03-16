# Meridian iOS App (Minimal)

Start Alert, End Alert. POSTs to kiosk API.

## Build for TestFlight

1. **Install kivy-ios** (macOS, Xcode required):

   ```bash
   brew install autoconf automake libtool pkg-config
   pip install Cython==0.29.33
   pip install kivy-ios
   ```

2. **Build toolchain** (first time only):

   ```bash
   cd /path/to/meridian
   toolchain build kivy
   ```

3. **Create Xcode project**:

   ```bash
   toolchain create MeridianAlert ios_app
   ```

4. **Open in Xcode**:

   ```bash
   open MeridianAlert-ios/MeridianAlert.xcodeproj
   ```

5. **In Xcode**:

   - Set **Bundle Identifier** (e.g. `com.yourdomain.meridianalert`)
   - Add **App Icon** (Assets.xcassets / AppIcon)
   - Select a **Signing** team
   - **Product → Archive**
   - **Distribute App** → TestFlight

## Run locally (desktop)

```bash
cd ios_app
python main.py
```

## Done when

A TestFlight build installs and launches without crashing. Tapping Alert shows "Alert sent!".
