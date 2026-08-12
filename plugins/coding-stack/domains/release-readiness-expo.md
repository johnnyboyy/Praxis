---
id: release-readiness-expo
subject: coding
universal: false
applies-when:
  - framework: expo
task-kinds: [create, change]
---

principles:

- id: ota-update-scope-excludes-native-changes
  rule: "When planning a release via EAS Update (or any Expo OTA update mechanism), treat OTA as scoped strictly to JavaScript and asset changes. Any change touching native modules — new permissions, new native libraries, native config — requires a full app-store build/review cycle; do not schedule it as an OTA release."
  condition: "Planning what a given change can ship through versus requiring a store submission, in an Expo project using EAS Update or a comparable OTA mechanism."
  reason: "OTA update mechanisms operate below the native binary boundary — they can replace the JS bundle and assets an already-installed binary loads, but cannot alter the binary itself. Assuming OTA can patch anything is a natural mistake once a team has shipped a few JS-only OTA fixes; the failure mode is discovering mid-release that a change requiring new native permissions or libraries can't ship the fast way, forcing an unplanned store-review cycle under release pressure instead of one accounted for at planning time."

- id: release-build-cannot-hot-reload-reuse-is-wrong-tool
  rule: "Before trusting what's rendered on a device/simulator as reflecting current source, confirm the installed build is a development client actively connected to Metro. A release/production build bakes its JS bundle in at build time; reconnecting, reloading, or reinstalling the same build is a no-op that will never show a source change made after that build was produced."
  condition: "Verifying a code change by running or screenshotting the app, or debugging 'my edits aren't showing up' — on any simulator, emulator, or physical device, local or cloud-hosted."
  reason: "A release build's JS is embedded at build time with no bundler connection. The app still runs and renders something real, just stale content — nothing errors to distinguish 'this is old' from 'this is current,' so the natural debugging instinct (reload, reinstall, restart Metro) all fail silently instead of surfacing that a dev-client build was never installed."

- id: eas-hosting-api-routes-run-on-workers-not-node
  rule: "Before relying on any Node.js-specific API inside an Expo Router API route (+api.ts) — fs, node-fetch, native Node crypto, long-running connections, or anything needing more than ~30s of CPU — verify it's available in the deployed runtime, not just in local npx expo serve. Use Web APIs and an edge-compatible database instead of filesystem or Node-only clients."
  condition: "Writing or reviewing an Expo Router API route intended for deployment via eas deploy / EAS Hosting."
  reason: "npx expo serve runs API routes locally under Node, so Node-only code executes fine locally — but EAS Hosting deploys the same routes to Cloudflare Workers, a runtime with no filesystem, no native Node modules, and a hard execution-time ceiling. Code passing every local test can fail only at deploy time or first production request."

- id: css-gradients-require-new-architecture
  rule: "Before using experimental_backgroundImage (CSS gradients), confirm the app is actually running on React Native's New Architecture (Fabric) and outside Expo Go — this feature has no defined behavior on the old architecture or in Expo Go."
  condition: "Any use of CSS-gradient style props (linear-gradient, radial-gradient) via experimental_backgroundImage."
  reason: "The experimental_ prefix specifically marks a Fabric-only gate, not a general instability warning. Reaching for it on the old architecture, or testing in Expo Go, produces a screen with no visible gradient and no explanatory error — a styling bug that reads as 'wrong syntax' rather than 'wrong runtime environment.'"

- id: expo-router-loader-request-object-mode-dependent
  rule: "In an Expo Router loader typed via LoaderFunction, always access the request parameter with optional chaining (request?.headers, request?.url) rather than assuming it exists — even if the current output mode is 'server' where it is populated."
  condition: "Writing or reviewing any Expo Router web loader that reads request, in a project that might run in or later switch to static output mode."
  reason: "request is fully populated in 'server' mode but always undefined in 'static' mode — the same loader code works in dev/server config and throws a null-dereference crash the moment output mode flips to static, a one-line config change with nothing at the call site enforcing which mode is active."

- id: liquid-glass-feature-detect-with-blur-fallback
  rule: "Never render GlassView (expo-glass-effect) unconditionally. Check isLiquidGlassAvailable() first and fall back to BlurView (or a solid background) when it's false."
  condition: "Any UI using expo-glass-effect's liquid glass backdrop."
  reason: "Liquid glass is an iOS 26+ system material with no cross-version emulation. Treating it as always-available silently couples the UI's correctness to the newest OS release; the break isn't caught by any build step, only by testing on a device that isn't on the latest OS."
