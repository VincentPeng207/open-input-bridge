# Open Input Bridge

**Use affordable, existing wireless input devices to control your computer.** Open Input Bridge is an independent, open-source bridging project, not a companion app for any proprietary device.

[简体中文](README.md) · [Download Android APK (Releases)](https://github.com/VincentPeng207/open-input-bridge/releases) · [Android source](android/README.md) · [Contributing](CONTRIBUTING.md) · [Verification](docs/VERIFICATION.md) · [Security](SECURITY.md)

**Important: the Windows receiver occupies TCP port `8766` by default.** If another application already uses it, **choose a different unused port yourself**, for example `.\start-windows.cmd --port 8767`. Open the freshly printed URL (with the **new port and token**) on Android. The receiver does not automatically select a new port or terminate unrelated programs. Allow the selected port only on a trusted private network.

## Feedback, devices and real-world needs

We'd love to learn about **the wireless controllers people actually use and the problems they want to solve**. You don't have to be using Open Input Bridge to share feedback. What Bluetooth rings, mini remotes, or other controllers have you tried? What would you like to control? What is frustrating about existing solutions?

- **Public questions, ideas and device discussions:** [GitHub Discussions](https://github.com/VincentPeng207/open-input-bridge/discussions)
- **QQ contact:** `2775818130` (for device experiences and user needs)

Please do not share token-bearing URLs or private information in public discussions. Your feedback helps prioritize future device integrations and interactions.

## What works today

The first integration is **LY-03 Bluetooth ring → Android phone (Open Input Bridge foreground App or foreground Chrome page) → trusted private LAN over HTTP/WebSocket → Windows Python receiver → keyboard shortcut**. The App and Chrome use the same browser event logic supplied by the Windows server.

The Windows receiver and Android Chrome route have **historical physical-device success reports**, but this migrated repository still needs fresh end-to-end acceptance. **Android App source and a Release debug APK are available; a user reported successfully downloading and using the app on 2026-11-03, although detailed gesture and lifecycle acceptance testing remains incomplete.** iOS, macOS, Linux receivers and other hardware are not supported or tested.

The middle button produces a configurable shortcut after a 300 ms single/double-click decision window; a detected quick double-click produces only Enter. Up/down actions map to eight ArrowUp/ArrowDown presses by default. Physical event detection depends on LY-03 firmware and Android input behavior: especially after device sleep, the first click may only wake the ring.

## Requirements

- Windows 10 or 11, Python **3.10+** with the `py` launcher (`py -3 --version`).
- Android phone with LY-03 paired through Android Bluetooth settings. Use **Open Input Bridge App (Android 14+)** or **Chrome** (the previously tested route).
- Both machines on the same trusted, mutually reachable private Wi-Fi/LAN.
- A ZIP extraction or Git checkout of the repository. The Windows receiver requires **no pip packages**; Chrome requires no Android installation, while the App route requires installing a debug APK.
- **Keep the Android phone unlocked, the screen on, and the bridge App or Chrome page visible and active in the foreground (topmost).** Lock-screen and background control are not supported. The App requests keep-screen-on while bridging, but the operating system may still interrupt it.
- The LY-03 can **go to sleep**. If button presses stop working, **press and hold the middle button for about 2 seconds to attempt wake/reconnection**, check Android Bluetooth connection status, then try a short click. Confirm behavior on your actual hardware.

## Safe first run

**If TCP port 8766 is occupied, change it explicitly**, for example:

```powershell
.\start-windows.cmd --port 8767 --dry-run
```

The Android URL must use the new port (`:8767`) and the token printed by the newly started receiver.

Open PowerShell in the repository root:

```powershell
py -3 .\windows\ly03_voice_bridge_ws_v1.py --dry-run --hotkey "ctrl+win" --copy-url
```

By default the receiver prints **one recommended private LAN URL**, such as `Open on PHONE: http://192.168.x.x:8766/?token=...`. Copy the **complete** URL (including port and token) into Android App settings or Chrome. Some machines have additional `172.16–31.x.x` addresses on VPNs or virtual adapters. If the suggested IP is not phone-reachable, run the receiver with `--show-all-addresses` to inspect all detected interfaces and check your networking. **An address recommendation does not prove Android reachability.** If Windows Firewall prompts, allow only **Private** networks. The phone page should show "在线" (online); manual test buttons should produce `DRY-RUN` logs. That online state does not prove the ring is connected.

Now pair/wear the LY-03, keep Android unlocked with the screen on, and **keep the bridge App or Chrome page in the foreground**. Press the **middle ring button** in the page's capture area; inspect `[BRIDGE] tap -> ... (DRY-RUN)`. A detected quick double-click should produce `double -> enter`; up/down commands should be logged. Manual test buttons confirm transport, **not** physical ring recognition.

## Android App: build and install

**The Android App is distributed as reviewable, unpackaged source code, not just an APK.** Inspect [MainActivity.java](android/app/src/main/java/org/openinputbridge/android/MainActivity.java), [AndroidManifest.xml](android/app/src/main/AndroidManifest.xml), and [Gradle build configuration](android/app/build.gradle). The HTML and JavaScript loaded by its WebView are also available in the Windows receiver's [`PAGE` source string](windows/ly03_voice_bridge_ws_v1.py). You can inspect, modify and compile the code yourself; the CI debug APK is optional and no APK binaries are committed. See [Android source and build guide](android/README.md).

**Option A — Open Input Bridge Android App (source included; physical LY-03 input pending verification):**

1. Requires **Android 14 (API 34) or newer**. Download the versioned APK directly from **[GitHub Releases](https://github.com/VincentPeng207/open-input-bridge/releases)** (the `android-v0.1.0-preview.1` prerelease or later Android prerelease), together with its SHA256 checksum and matching source snapshot. As an alternative, the [Android build workflow](https://github.com/VincentPeng207/open-input-bridge/actions/workflows/android.yml) retains short-lived CI artifacts. **This is a debug-signed test build, not a store release or hardware-verified product.** Check its origin and Android sideload warning.
2. Pair the LY-03 in Android Bluetooth settings; launch **Open Input Bridge**, paste the Windows receiver's **complete current URL, including `?token=...`**, into the app's settings, and tap the connect button.
3. **Keep the App topmost, visible, and active, with the phone unlocked and screen on.** The bridge page requests keep-screen-on. Switching apps, losing focus or locking the phone stops forwarding; returning to the App reloads the bridge.
4. Use the page's manual test buttons, then the actual ring in `--dry-run` mode. **Building the APK does not establish that WebView captures LY-03 input correctly.** Compare with Option B when troubleshooting.

**Option B — Chrome (the historically tested route):** Pair the ring with Android and open the Windows receiver's complete current LAN URL in **Chrome**. Keep the phone **unlocked, screen on and the Chrome bridge page visible in the foreground**. Test the page buttons, then the physical ring. No App installation required.

For local Android builds, install **JDK 17, Gradle 8.10.2 and Android SDK Platform 35**; from `android/`, run `gradle :app:assembleDebug --no-daemon`. Output: `android/app/build/outputs/apk/debug/app-debug.apk`. More information is in [android/README.md](android/README.md).

## Send real keys

Stop the server with Ctrl+C; restart **without** `--dry-run`:

```powershell
py -3 .\windows\ly03_voice_bridge_ws_v1.py --hotkey "ctrl+win" --copy-url
```

Enter the **new** full URL in the Android App settings or reopen it in Chrome. Every receiver launch generates a **new random token**; old URLs cannot reconnect. Give the intended Windows program keyboard focus. **In your voice input application's own settings, configure its start/stop dictation shortcut to Win + Ctrl (`Ctrl+Win`)**, matching this bridge's default. This is **not** a built-in universal Windows dictation shortcut. If you choose a different combination in the voice input app, also change the receiver's `--hotkey` argument (for example, `--hotkey "ctrl+shift+v"`). A second normal single click seconds later can toggle dictation again; a **quick middle double-click** is a separate gesture that sends **Enter** by default, which may finalize dictation or send a chat message depending on the app.

To verify input injection without voice software, use `--hotkey "ctrl+a"` instead, type some text into Notepad and focus it: one middle click should select all text. A recognized quick double-click sends Enter (visible effect depends on selection/focus). Then switch to the shortcut configured in your actual application.

Use `start-windows.cmd` in the repository root for safe restarts; it defaults to `ctrl+win` and clipboard copying. From a terminal, `.\start-windows.cmd --dry-run` runs safe mode, or `.\start-windows.cmd --hotkey "ctrl+a"` overrides the shortcut. **The launcher automatically replaces an old listener only when its process command line identifies the exact bridge script in this checkout.** If the port belongs to any other application or a different checkout, it reports an error without terminating it. Running the Python script directly does not perform this replacement. **Every restart requires opening the new token-bearing URL on Android.**

## Commands and limitations

| Input | Desktop output |
| --- | --- |
| Middle single click (`tap`) | Configured `--hotkey`, after ~300 ms |
| Middle quick double (`double`) | Enter only |
| Up (`up`) | ArrowUp × 8 by default |
| Down (`down`) | ArrowDown × 8 by default |

Options include `--scroll-steps 1..16`, `--swipes pages` (PageUp/PageDown), `--swipes ignore`, `--port 8767`, and `--bind 127.0.0.1` for local-only testing. Older `up_double/down_double` messages remain recognized for protocol compatibility, but **this browser client does not emit directional double-click commands**.

The client **never queues or replays offline key events**. **Android lock-screen or loss of foreground focus disables forwarding**; Windows sleep, unstable Wi-Fi and LY-03 device sleep also interrupt control. To try waking/reconnecting the ring, hold its middle key for **about 2 seconds**, verify the Android Bluetooth connection, then click normally. The app/webpage reporting online alone does not prove the ring is connected. Real-world double-click detection varies by device/firmware.

## Troubleshooting

- **Phone cannot open the page**: check the receiver, the phone URL's port, reachable private LAN, and Private firewall permissions. First use the recommended IPv4; if it fails, add `--show-all-addresses` to inspect the interface candidates. Avoid the computer's `127.0.0.1` and Wi-Fi client isolation.
- **403 or repeated disconnections**: reopen the **fresh complete URL** with its new token after restarting Windows; use `http://` (the page establishes same-origin `ws://`).
- **Manual buttons work but ring does not**: check Android Bluetooth pairing, that the screen is **unlocked and on**, and the Android App/Chrome bridge **remains topmost and active**. After ring sleep, hold the middle key **about 2 seconds** to attempt reconnection, then retry; verify on your device.
- **Only DRY-RUN logs**: restart without `--dry-run`, reopen the new phone URL, focus the Windows target, and confirm the voice input application's start/stop hotkey matches `--hotkey` (default `ctrl+win`).
- **TCP port 8766 busy**: the launcher can safely replace an older receiver from the same checkout. Otherwise choose an unused port yourself, e.g. `.\start-windows.cmd --port 8767` (or `--port 8767` with the Python command), and use the new URL on Android. It never terminates unrelated listeners.
- **SENT but no action**: test Notepad with `ctrl+a`; elevated windows or shortcut conflicts may reject synthetic keys.

## Tests, extension and licensing

Python runtime has **no third-party package dependencies**. Optional **Node.js 18+** is needed for browser JS regression tests:

```powershell
py -3 -B -m unittest discover -s windows -p "test_*.py" -v
node .\windows\test_directional_classifier.js
```

Without Node.js, Python's JS-related tests skip. Automated tests and CI cannot replace actual Android/LY-03/Windows acceptance testing. See [verification matrix](docs/VERIFICATION.md) and [contribution guide](CONTRIBUTING.md) for adding device adapters without destabilizing the proven path.

For security, use **trusted private LANs only**: HTTP/WS is **unencrypted**, and a random per-launch URL token protects a strict command allowlist. Never forward the listening port to the Internet or publish the token URL. See [SECURITY.md](SECURITY.md).

The Android App is under [android/](android/README.md), including build instructions and physical acceptance status. MIT-licensed; device trademarks belong to their respective owners. This project is not affiliated with or endorsed by the LY-03 manufacturer.
