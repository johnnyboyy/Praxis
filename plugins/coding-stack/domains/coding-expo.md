---
id: coding-expo
subject: coding
universal: false
applies-when:
  - framework: expo
task-kinds: [create, change]
---

principles:

- id: expo-router-typed-routes-for-link-safety
  rule: "Enable Expo Router's Typed Routes (the `experiments.typedRoutes` config) so that a broken navigation link — a route that was renamed, moved, or never existed, or a path whose params don't match — is a TypeScript compile error rather than a silent runtime failure."
  condition: "Any Expo/React Native project using Expo Router's file-based routing, especially once route files get refactored, renamed, or moved after initial creation."
  reason: "File-based routing decouples a route's identity from any import statement — routes are referenced elsewhere only as string paths (`Link href`, `router.push`), which normal TypeScript checking does not validate. Moving or renaming a route file leaves those string references stale with no compiler signal; the break only surfaces when a user actually navigates that path. Typed Routes closes exactly this gap by checking route strings against the actual file tree at compile time — the error-exposing-form choice applied specifically to route paths, since the convenience of plain strings and the safety of type-checked ones produce the same successful build until the untyped path is actually hit."

- id: expo-router-default-react-navigation-for-low-level-native-control
  rule: "Default to Expo Router for a new Expo/React Native project's navigation. Reach for bare React Navigation instead only when the project needs something Expo Router's conventions don't expose — heavily customized transitions/gestures, integrating navigation into an existing (brownfield) native app, or deliberately avoiding the Expo SDK ecosystem."
  condition: "Choosing or migrating a navigation library for an Expo/React Native project."
  reason: "Expo Router is built on top of React Navigation, not a replacement for it — it adds file-based routing conventions (folder structure doubles as the route table), automatic deep-linking, and web-route parity for every screen without extra configuration. Bare React Navigation requires imperative navigator setup and manual deep-linking wiring, but keeps direct, low-level control over navigator behavior. The conventions that make Expo Router faster for the common case are the same conventions that get in the way of the uncommon case (custom transitions/gestures, non-Expo native integration) — so the choice tracks how much of that low-level control the project actually needs, not a blanket 'newer is better' preference."

- id: interop-layer-does-not-cover-native-code-dependencies
  rule: "When a framework provides a backward-compatibility interop layer for a breaking architectural change, do not assume it covers every third-party dependency uniformly. Verify dependencies that ship native code individually — the interop layer's guarantee is explicitly weaker for those than for pure-JS libraries."
  condition: "Evaluating third-party library compatibility during a framework-level architecture migration that ships an interop/compat shim (e.g. React Native's New Architecture interop layer for old-architecture libraries)."
  reason: "Expo's own documentation states the interop layer 'is not perfect and some libraries will need to be updated' — the failure cases named are specifically libraries shipping native code, not JS-only ones. Treating the interop layer as a blanket guarantee papers over exactly the class of dependency most likely to fail, deferring discovery from migration time to a runtime crash."

- id: expo-router-no-direct-react-navigation-imports
  rule: "In an Expo Router project on SDK 56 or later, do not import navigation primitives directly from `@react-navigation/*`. Use Expo Router's own exports even for code that previously worked by importing straight from React Navigation."
  condition: "Expo SDK 56+ project using Expo Router, especially code or copied examples predating SDK 56 that imported navigation primitives directly from `@react-navigation/*` because Expo Router used to re-export/borrow them from that library."
  reason: "As of SDK 56, Expo Router forked the navigation primitives it previously borrowed from React Navigation, specifically to avoid two divergent navigation libraries coexisting inside the same app. A direct `@react-navigation/*` import that worked before SDK 56 now resolves to a library whose primitives are no longer the ones Expo Router's own navigator instantiates — the failure is a silent behavioral mismatch (state desync, missing navigation context) rather than an explicit deprecation error, so it surfaces at runtime, not at the import site."

- id: expo-native-dirs-generated-not-hand-edited
  rule: "In an Expo project using Continuous Native Generation (CNG — the `npx expo prebuild` workflow), treat `ios/` and `android/` as generated build output, never as source to hand-edit. Make native-level customizations through config plugins that act on `app.json`/`app.config.js` (modifying `Info.plist`, `AndroidManifest.xml`, Gradle config, etc. at generation time), not by editing the generated native files directly."
  condition: "Any Expo project running the CNG/prebuild workflow that needs a native-level customization — permission entries, native SDK config, build-time native code hooks — whether building locally (`npx expo run:[ios|android]`) or via EAS Build's cloud VMs."
  reason: "`npx expo prebuild` regenerates `ios/` and `android/` from `app.json`/`app.config.js` plus installed config plugins (`@expo/prebuild-config`, `@expo/config-plugins`) every time it runs — including on every EAS Build invocation, which always prebuilds from a clean checkout. A hand-edit made directly to the generated directories is silently discarded on the next regeneration, with no error at edit time or build time to signal the loss — the customization simply isn't there anymore. This is the same failure shape scripts-over-hand-editing-structured-data names for any generated artifact edited at its output instead of its source: the generator is the durable location for the change, and a config plugin is that location for native customizations in a CNG Expo project specifically. Committing generated ios/android directories to version control compounds the risk by making the stale hand-edit look authoritative to anyone reading the repo."

- id: expo-inline-native-modules-before-ejecting
  rule: "In an Expo SDK 56+ project needing native functionality with no existing Expo/community module for it, write the native code as an inline Swift/Kotlin file under a `watchedDirectories` folder and run `npx expo prebuild`, rather than ejecting the app or scaffolding a standalone native module package."
  condition: "A small-to-medium native capability (custom haptics, biometric auth, on-device ML, Bluetooth/NFC access, etc.) is needed in an Expo project targeting SDK 56 or later, and no existing library covers it."
  reason: "Before SDK 56, adding native code meant either fully ejecting (losing the managed workflow) or building a separate native module package with its own Podfile/Gradle scaffolding — both expensive enough relative to staying JS-only that teams often reached for JS workarounds even when native code was the better fit. Inline native modules remove that setup cost: the file lives next to the TypeScript it serves, autolinking and TypeScript type generation (`expo-type-information`) happen automatically on prebuild, and `requireNativeModule` is the only manual wiring left. Collapsing the cost from 'days of setup' to 'one file and a prebuild' changes the actual build-vs-workaround decision for capabilities that weren't previously worth the ceremony."

- id: no-color-platformcolor-values-in-reanimated-styles
  rule: "Never pass a Color (from expo-router) or PlatformColor value into a Reanimated useAnimatedStyle or any shared-value-driven style. Use a static color string/value on the animated path instead."
  condition: "Any Reanimated-driven animation whose style includes a color — entering/exiting animations, useAnimatedStyle, withTiming/withSpring targets."
  reason: "Color/PlatformColor are opaque platform-resolved handles, not interpolable JS values. Reanimated's worklets run on the UI thread operating on values it can serialize and interpolate directly; handing it an opaque platform color reference breaks that assumption with no clear error — the failure surfaces as a wrong or missing color in the animated output, not at the point the value was passed in."

- id: medialibrary-save-requires-local-file-not-base64
  rule: "Before calling MediaLibrary.saveToLibraryAsync with an image that originated as a base64/data-URI string (AI-generated images, canvas exports, API responses), decode it and write it to a local file first (e.g. expo-file-system's File API), then pass that file's uri — never the base64 string itself."
  condition: "Saving any image to the device media library whose source is base64-encoded rather than an existing local file path."
  reason: "MediaLibrary.saveToLibraryAsync only accepts local file paths; it has no code path for inline image data. Because a base64/data URI superficially resembles a valid string argument, this is an easy step to skip, and the API gives no forgiving fallback."

- id: blurview-requires-overflow-hidden-for-rounded-corners
  rule: "When applying borderRadius to a BlurView (expo-blur), also set overflow: 'hidden' on it."
  condition: "Any rounded-corner BlurView usage."
  reason: "BlurView's blur renders as a native effect layer that isn't clipped by borderRadius the way ordinary View content is. Without overflow: 'hidden', the blur draws past the rounded corner as a visible square edge — a purely visual bug with no error, warning, or type signal."

- id: expo-go-default-until-native-code-needed
  rule: "Default to Expo Go for development. Move to a development client (eas build --profile development / expo run:ios/android) as soon as the project needs local native modules, Apple targets (widgets, app clips, extensions), a third-party native module Expo Go doesn't bundle, config plugins, or remote push/Universal Links testing — decide this at scoping time, not only once a build has already failed inside Expo Go."
  condition: "Deciding or reviewing a project's dev workflow, at project start and again whenever a new capability is being added."
  reason: "Expo Go is a fixed native binary bundling a specific set of pre-linked native modules; it cannot load native code it wasn't built with, and a custom build commits the project to a slower prebuild + native-toolchain iteration loop. Treating Expo Go as default until something visibly breaks means the mismatch is discovered mid-feature-work rather than anticipated at scoping time; defaulting to a custom build when Expo Go would have covered it pays that slower loop for no benefit, with no natural moment surfacing the mistake."

- id: expo-ui-list-not-virtualized-avoid-for-large-lists
  rule: "Reach for @expo/ui's List/ListItem (universal) or LazyColumn (Jetpack Compose) for short, static lists (settings screens, field groups, small bounded collections) — not as a drop-in replacement for FlatList/FlashList when the dataset is large or unbounded."
  condition: "Choosing a scrollable-list component for any dataset that isn't small and fixed, or redesigning a web data feed/table as a native screen."
  reason: "Despite the naming parallel to virtualized native list views, each row in @expo/ui is a JSX node processed on the JS thread — no native-side virtualization/recycling. The component works correctly in dev with a small seed dataset and only degrades to jank at production scale, so the mistake isn't caught until real data volume."

- id: expo-router-toolbar-children-not-behind-wrapper
  rule: "When extracting Stack.Toolbar buttons/menus into a separate reusable component, have that component return its own <Stack.Toolbar> wrapping the Button/Menu elements — never export a component that returns bare Stack.Toolbar.Button/Menu elements intended to be spread as children of a Stack.Toolbar rendered elsewhere."
  condition: "Refactoring or componentizing Expo Router's Stack.Toolbar-based header/toolbar UI."
  reason: "Expo Router introspects Stack.Toolbar's direct children to build native toolbar configuration rather than rendering it as an ordinary tree. An intermediate component between Stack.Toolbar and its children breaks that introspection silently — the buttons simply don't appear, with nothing else visibly wrong."

- id: expo-router-array-group-for-shared-tab-screens
  rule: "When two or more tabs need to push the exact same screen(s) with a shared, coherent back-stack, use an array group route (app/(tabA,tabB)/screen.tsx with explicit unstable_settings anchors) rather than duplicating the screen file inside each tab's own folder."
  condition: "Designing tab navigation where a detail or shared screen must be reachable identically from multiple tabs."
  reason: "Duplicating a screen file per tab creates two independent route identities for conceptually one screen — each copy carries its own navigation state, so back-stack behavior and screen-local state can diverge between tabs even though the user experiences 'the same page.'"

- id: native-tabs-must-be-statically-defined
  rule: "Treat the set of NativeTabs.Trigger children as fixed at first render. Don't conditionally add or remove tabs based on runtime state (auth resolving after mount, a feature flag loading async, etc.) — decide the tab set once during initial render, and use the hidden prop on a Trigger if a tab must sometimes not appear."
  condition: "Any NativeTabs layout whose tab visibility could plausibly depend on data that resolves after mount."
  reason: "NativeTabs is backed by a native tab-bar controller; changing the number or identity of Trigger children remounts the entire tabs navigator, dropping every per-tab navigation stack and any screen-local state — a full, silent reset of app navigation state triggered by what reads in the JSX as an ordinary conditional render."

- id: native-tabs-bottomaccessory-state-outside-component
  rule: "A component rendered inside NativeTabs.BottomAccessory must not hold its own useState (or other local render state) as its source of truth for anything that needs to stay consistent across layouts — lift that state to a prop, context, or external store the component reads from."
  condition: "Implementing NativeTabs.BottomAccessory content (e.g. a mini-player) that needs to reflect a single, consistent piece of state."
  reason: "BottomAccessory's content mounts as two simultaneous instances — one for 'regular' and one for 'inline' placement — not one. Local component state diverges between the two instances since each holds its own independent copy; whichever becomes visible on placement switch can present a stale or reset value, with no signal that two copies existed."

- id: native-tabs-transparency-requires-first-opaque-child-not-collapsed
  rule: "For a NativeTabs screen relying on scroll-edge tab-bar transparency (iOS 18 and earlier), ensure the ScrollView/FlatList is the literal first child in the native view tree. If it must be wrapped in an intermediate View, mark that wrapper collapsable={false}; otherwise use disableTransparentOnScrollEdge instead of relying on automatic detection."
  condition: "NativeTabs screens on iOS 18 or earlier using scroll-driven tab-bar transparency, wrapping their ScrollView/FlatList in any additional View."
  reason: "React Native's release-build renderer strips (collapses) wrapper Views carrying no styling/behavior of their own as a performance optimization. A wrapper that looks present in JSX may not exist in the actual native view hierarchy the tab bar's transparency detection walks — reproducing only in optimized builds where collapsing actually happens, not in dev."

- id: zoom-transition-dismissal-bounds-for-inner-scrollview
  rule: "When an Apple Zoom transition destination screen contains its own scrollable content, set usePreventZoomTransitionDismissal's unstable_dismissalBoundsRect to the non-scrolling region of the screen, rather than leaving the default whole-screen dismissal gesture area in place."
  condition: "Link.AppleZoom destination screens (iOS 18+, Stack navigator) that also contain an interactive scroll view."
  reason: "The zoom transition's default swipe-to-dismiss gesture and an inner scroll view both claim vertical swipes over the same region. Left at default, the system's gesture-arbitration can make the scroll view swallow the dismiss gesture (or vice versa) — reads to the user as a broken screen rather than two gestures coexisting."

- id: formsheet-detent-index-controls-background-interactivity
  rule: "When a multi-detent form sheet should let the user interact with content behind it at its smaller detents (e.g. panning a map) but dim/block it at the largest, explicitly set sheetLargestUndimmedDetentIndex to the index of the last detent that should remain interactive."
  condition: "Form sheets with 2+ entries in sheetAllowedDetents, presented over interactive background content."
  reason: "Expo Router's form sheet dims and blocks the background at every detent by default. A sheet meant to let the user interact with content behind it will otherwise trap all touches regardless of how little screen it covers — visible only as 'the background stopped responding,' with no exception or warning."

- id: dom-component-router-hooks-not-callable
  rule: "Never call useLocalSearchParams(), useGlobalSearchParams(), usePathname(), useSegments(), useRootNavigation(), or useRootNavigationState() inside a DOM component ('use dom'). Read the values in the native parent screen and pass them down as props instead."
  condition: "Any DOM-shelled screen or DOM component that needs the current route's params, pathname, or navigation state."
  reason: "Those hooks require synchronous access to native routing state a JS-context-isolated webview cannot reach — while Link and useRouter do work since they only dispatch navigation actions outward. The call doesn't throw or warn, it just silently doesn't work inside the isolated runtime, so the screen renders with missing/undefined values with nothing pointing at the cause. The two hook families look interchangeable from the API surface, making this a natural mistake."

- id: layout-route-cannot-be-a-dom-component
  rule: "Never make an Expo Router _layout file a DOM component. Layout routes must stay native; port web-only layout logic using native APIs instead of trying to shell the layout itself."
  condition: "Migrating a Next.js/web app's root or nested layout to Expo Router as part of a web-to-native migration."
  reason: "A layout route is the native shell that hosts everything beneath it, including any DOM-component children — it cannot itself be the thing being hosted. This is a structural dead end discovered only once nothing renders."

- id: streaming-fetch-requires-expo-fetch-not-rn-fetch
  rule: "For any code path reading a streaming HTTP response (SSE, or the Vercel AI SDK's useChat), use expo/fetch on native, not React Native's built-in fetch or a direct port of the web fetch call."
  condition: "Porting a web feature that depends on streamed responses (chat UIs, live token generation, SSE) to native."
  reason: "React Native's built-in fetch cannot read a streaming response body at all — a ported call doesn't error, it just never receives incremental chunks, looking like a hang or empty response rather than an unsupported-API error."

- id: nativewind-inline-variables-breaks-platform-color
  rule: "When configuring NativeWind v5's Metro transformer (withNativewind), explicitly set inlineVariables: false. Do not accept the default or copy a config that leaves it unset."
  condition: "Any Expo project using NativeWind v5 / react-native-css with metro.config.js's withNativewind wrapper, especially one that also uses platformColor() CSS variables."
  reason: "NativeWind's inline-variables optimization resolves CSS custom properties into static values at build/transform time — incompatible with platformColor(), whose value must stay a live native color reference resolved by the OS (dark mode, accessibility contrast). Leaving the default on silently breaks any CSS variable feeding a platformColor, since nothing errors — the color just stops responding to OS-level changes."

- id: expo-router-loader-data-cached-for-session
  rule: "When using Expo Router web loaders (useLoaderData, SDK 55+), do not assume a client-side navigation back to a previously-visited route re-runs its loader and returns fresh data. Loader data is cached for the browser session — treat any route whose data can go stale within a session as needing its own explicit refetch/invalidation."
  condition: "An Expo Router web app (server or static output mode) using loaders for a route whose underlying data can change while the user's session is open."
  reason: "The docs name this as a known limitation, not a documented cache-control knob. Assuming loader data refreshes on every visit produces a UI silently showing stale data on a route revisit — surfacing only once the session is long enough for the data to have changed."

- id: expo-ui-platform-specific-import-crashes-wrong-platform
  rule: "Never import from @expo/ui/swift-ui in code that can run on Android, or from @expo/ui/jetpack-compose in code that can run on iOS — including a shared route file with no platform guard. Isolate each in its own .ios.tsx/.android.tsx file outside the route tree, or gate behind Platform.OS in the same file."
  condition: "Any file that imports from a platform-specific @expo/ui sub-package."
  reason: "These sub-packages register native view configs that only exist on their own platform; importing either on the wrong platform crashes at runtime with an 'Unable to get view config' error rather than failing at build time, since the import resolves fine in JS and only native view registration fails when the component tries to mount."

- id: expo-router-no-platform-extension-route-files
  rule: "Never place a .ios.tsx or .android.tsx file inside Expo Router's app/ (or src/app/) directory. Put platform-specific component files in a non-route directory and import them from a plain route file, or branch on Platform.OS within a single non-suffixed route file."
  condition: "Any Expo Router project introducing a platform-specific implementation for a screen."
  reason: "Expo Router's file-based routing doesn't support platform-extension suffixes for route files — a .ios.tsx inside app/ isn't treated as one variant of a route, it's read as defining a route with no fallback sibling, throwing a Render Error. Route resolution and Metro's platform-extension resolution answer two different questions about the same filename pattern."

- id: expo-ui-usenativestate-silently-degrades-without-worklets
  rule: "When using @expo/ui's useNativeState for synchronous, flicker-free UI-thread updates (e.g. a masking/formatting text field), confirm react-native-worklets is installed and the update handler is actually marked 'worklet'. Do not assume the synchronous behavior is active just because useNativeState/ObservableState is being used."
  condition: "Any component relying on useNativeState specifically for its synchronous, no-React-render update guarantee."
  reason: "Without react-native-worklets, the 'worklet' directive has no effect and updates fall back through the normal React render cycle — the code runs without error, but the specific problem useNativeState was reached for (flicker) silently persists, easy to misdiagnose as a limitation of the API itself rather than a missing prerequisite."

- id: native-consumed-tree-refactors-not-semantics-preserving
  rule: "When a native layer consumes the React tree structurally — introspecting direct children, binding a native controller to the child set, mounting one child in multiple native placements, collapsing styling-free wrappers, or deriving identity from file placement — ordinary composition refactors are not semantics-preserving. Before wrapping, extracting into a component, conditionally rendering, duplicating, or platform-suffixing anything such a layer consumes, check whether direct-childness, static identity, single-instance state, or file placement is load-bearing to the native side, and preserve it."
  condition: "Refactoring or componentizing JSX or route files consumed by a native-backed container (navigator, tab bar, toolbar, sheet, accessory slot) in Expo/React Native — anything that reads the tree rather than rendering it. Fires on novel containers the named instances do not cover."
  reason: "Every instance of this failure is silent: the refactor reads as standard React composition, compiles cleanly, and the broken contract is invisible in JS — buttons vanish, navigation state resets, accessory state forks, a wrapper exists in JSX but not in the release view hierarchy. The transferable judgment is that this-is-just-an-extract-component-refactor is not a safe assumption anywhere a native layer reads the tree instead of rendering it."
