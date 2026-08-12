---
id: dependency-management-expo
subject: coding
universal: false
applies-when:
  - framework: expo
labels: [dependency-management]
---

principles:

- id: pin-multi-package-versions-for-native-graphics-stack
  rule: "When integrating a from-scratch native GPU/graphics stack built from several young, tightly-coupled libraries (e.g. react-native-wgpu + three.js + @react-three/fiber + wgpu-matrix), pin exact tested-compatible versions across all of them rather than letting each package's own semver range resolve independently, and re-verify the whole set together before bumping any single package."
  condition: "Adding or upgrading WebGPU/Three.js/react-three-fiber (or a comparable emerging, multi-package native-bridge integration) in an Expo project."
  reason: "The real compatibility contract between these packages isn't expressed in any one package's own semver range — a version bump in one can silently break the FFI/type contract with the others even though npm install succeeds and each package's own constraints are individually satisfied. The failure surfaces as type errors or runtime crashes discovered only by running the app, not by dependency resolution."

- id: expo-filesystem-migrate-once-feature-gaps-close
  rule: "Re-evaluate a deferred migration off Expo's legacy FileSystem API once a release closes the specific feature gaps that justified staying on it (e.g. download progress reporting, cancellation via AbortSignal, an explicit overwrite flag on copy/move) — don't let the migration stay deferred by default once the blocking reason is gone."
  condition: "A project still on Expo's legacy FileSystem API specifically because the new API previously lacked a feature the project needs (progress reporting, cancellation, overwrite control), evaluated at each Expo SDK upgrade."
  reason: "A deferred migration is only correctly deferred while its blocking reason holds. SDK 56 closes the FileSystem API's most commonly cited feature gaps — treating the original 'the new API can't do X yet' justification as still valid without rechecking it is the same silent-drift failure as an unreviewed ceiling comment: the condition that justified the exception can become false with nobody rechecking it."

- id: expo-sequential-sdk-upgrade-across-router-fork
  rule: "When upgrading an Expo project from SDK 54 or earlier to SDK 56, upgrade one major SDK version at a time (54→55→56) rather than jumping directly, even though the standard upgrade command will attempt the direct jump."
  condition: "Expo project upgrade spanning SDK 56's Expo Router fork — i.e., starting from SDK 54 or earlier."
  reason: "SDK 56 forked Expo Router's navigation internals out of `@react-navigation/*`, changing the navigation dependency tree in a way direct 54-to-56 upgrades don't handle correctly; the intermediate SDK 55 step is what lets dependency resolution and codemods catch up incrementally. Skipping it converts a known, documented upgrade path into an unverified one — the failure surfaces mid-upgrade instead of being avoided by following the supported path. This is a distinct risk from the import-rewrite mechanics of the fork itself (already captured in expo-router-no-direct-react-navigation-imports)."

- id: expo-sdk56-fetch-default-swap-breaks-oauth
  rule: "Before or while upgrading to Expo SDK 56, explicitly test any code path that depends on precise `fetch` behavior — especially OAuth token exchange or third-party SDKs with their own fetch expectations (crash reporting, auth libraries) — because SDK 56 replaces the global `fetch` with `expo/fetch`, a differently-behaved implementation. Use the `EXPO_PUBLIC_USE_RN_FETCH=1` fallback as a temporary stopgap only, not a permanent fix, while dependencies catch up."
  condition: "Expo project upgrading to SDK 56 whose code or dependencies perform OAuth flows, use libraries with documented fetch-behavior assumptions, or otherwise rely on the platform's global fetch implementation matching prior behavior."
  reason: "A global-fetch swap is invisible in application-code diffs — nothing a developer wrote changed — but it alters runtime behavior everywhere fetch is used, so the risk stays silent until the specific flow depending on old behavior is actually exercised. Real breakages from exactly this change (an AT Protocol OAuth client, a crash-reporting SDK's compatibility issue) show the failure mode is concrete, not hypothetical. Treating a global runtime substitution shipped as a default upgrade the same as an opt-in feature is the mistake; it needs the same behavioral verification a manual dependency swap would get."

- id: codemod-deprecation-check-after-rewrite
  rule: "After a codemod or scripted import rewrite completes cleanly, check each rewritten symbol for a @deprecated tag or runtime deprecation warning before treating the migration as finished."
  condition: "Any automated or semi-automated import-rewrite migration that resolves imports to a compatibility/interop module — e.g. the Expo SDK 56 @react-navigation/* → expo-router import rewrite."
  reason: "A codemod's success criterion is 'does this compile and resolve,' not 'is this the currently recommended API' — an import can resolve cleanly to a deprecated shim kept only for backward compatibility, which passes typecheck and build but silently leaves the project one step behind, discovered again at the next upgrade cycle when the shim may be removed outright."

- id: escalate-unmapped-symbols-dont-diy-workaround
  rule: "If a @react-navigation/* symbol has no expo-router replacement during this migration, don't invent a local workaround (a shim, a re-export, a copied implementation) to keep the old symbol alive. Ask the user to file an issue upstream describing what's needed, and treat the symbol as blocked until a real replacement exists."
  condition: "Performing the SDK 56 react-navigation-to-expo-router import migration and encountering a symbol not covered by the manual mapping table or the codemod."
  reason: "A hand-rolled workaround creates project-specific technical debt that has to be undone later when the framework adds real support, and risks diverging from the eventual official API. Filing upstream keeps the project on the framework's supported surface and turns an invisible local patch into a visible, trackable blocker."

- id: reanimated-worklets-new-required-peer-post-newarch
  rule: "After a major framework or architecture upgrade, explicitly check whether libraries already in the project gained new required peer dependencies — don't rely on a dependency audit that only checks direct imports against package.json."
  condition: "Any Expo SDK upgrade crossing SDK 54 in a project using react-native-reanimated, where react-native-worklets became a required (no longer bundled) peer dependency under the New Architecture — and more generally, any major framework upgrade where a previously-bundled capability of an existing dependency splits out into its own required peer package."
  reason: "A project that upgrades cleanly can still have a dependency silently fail at first use: a missing new peer dependency shows up as a native-module resolution failure, not a JS-level one caught by typecheck. This is the forward-migration mirror of auditing transitive dependencies after a major upgrade."

- id: root-stack-vs-js-stack-codemod-collision
  rule: "When migrating @react-navigation/* imports to expo-router on SDK 56+, never rewrite `import { Stack } from 'expo-router'` to `expo-router/js-stack`."
  condition: "Running or reviewing the SDK 56 @react-navigation/* → expo-router import migration, whether via the automated codemod or a manual pass, specifically for files importing the root layout Stack component."
  reason: "The root Stack from expo-router is the file-based layout component used in route files — a different thing from expo-router/js-stack's JS stack navigator (the replacement for @react-navigation/stack). The two Stack exports are unrelated APIs sharing an identifier, so a naive global replace (or codemod bug) treating every Stack import identically would silently point layout-file Stack usage at the wrong module — an error a diff review focused on 'did the import path change' would not catch without knowing this distinction exists."

- id: expo-av-video-android-parity-gap-fails-silently
  rule: "When migrating from expo-av to expo-video, explicitly test the Android build, not just iOS — known migration issues (both packages installed simultaneously causing a black VideoView; the same player mounted in multiple VideoViews at once; setting player.currentTime inside the useVideoPlayer setup callback) are Android-specific, work fine on iOS, and fail as a blank video view with no thrown error."
  condition: "Migrating video playback from expo-av to expo-video, at the point of verifying the migration on both platforms."
  reason: "Every named failure mode is a silent visual regression (black screen) rather than an exception, and every one is Android-only — a migration verified only on iOS will pass cleanly and still ship a broken video screen on Android."
