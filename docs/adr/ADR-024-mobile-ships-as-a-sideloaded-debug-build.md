# ADR-024: Mobile ships as a sideloaded debug build

**Status**: ACTIVE
**Type**: adr
**Last Updated**: 2026-10-21

> Drift trap for this type: Being *edited* to look correct in hindsight. An ADR that is rewritten to match current reality destroys the only record of why the decision was made.

---

## Context

JARVIS is served to a phone in two ways: as a PWA, and as an Android APK built
from the same web console with Capacitor. The APK exists because a PWA cannot do
everything the phone client needs — notably background push handling and a
launcher presence.

Two properties of the build are deliberate and neither is a default that was
overlooked:

- **It is a debug build.** `mobile/package.json` defines exactly one build path,
  `build-apk`, which runs `sync-www.js && npx cap sync android && ./android/gradlew
  -p android assembleDebug`. There is no `assembleRelease`, no signing config and
  no Play Store listing.
- **Mixed content is allowed.** `mobile/capacitor.config.json` sets
  `android.allowMixedContent: true`, so HTTP subresources load inside the app
  WebView.

The application is `dev.jarvis.app`, `versionCode 1`, `versionName "1.0"`, with
`minifyEnabled false`.

## Decision

**Build for one device, by hand. Do not produce a release build, do not sign,
and do not distribute.**

The APK is a personal client for a self-hosted server. It is produced by a single
command, installed by sideload, and never leaves the operator's device. The
WebView is allowed to load mixed content because the server it talks to may be
reached over plain HTTP on a local network.

## Alternatives considered

1. **A signed release build published to the Play Store.** Rejected: it is a
   client for one person's server, with no account system, no multi-tenancy and
   no support model. Play review would also require a privacy policy for an app
   whose entire backend is a private host.

2. **A release build sideloaded, without Play.** Rejected as cost without
   benefit: it needs a keystore, a signing config and a rotation procedure to
   produce an artifact installed on one phone. `minifyEnabled false` also means
   the release build would not shrink meaningfully.

3. **`allowMixedContent: false` and HTTPS everywhere.** Rejected for now: the
   deployment reaches the server over Tailscale, and requiring TLS on that path
   means certificate management for an internal address. Setting it `false`
   would break the local-network case without removing the underlying trust
   assumption — the operator owns both ends.

4. **Ship only the PWA, no APK.** Rejected: it was the starting point, and the
   APK exists because the PWA could not do what was needed on the device.

5. **A native Android app rather than a Capacitor wrapper.** Rejected as
   disproportionate: the console already exists as a web application, and a
   second implementation would be a second thing to keep in step.

## Consequences

### Positive

- **One command builds the client**, and it reuses the exact web console the
  browser serves — there is no second UI to keep in sync.
- **No signing keys to manage, store or rotate.** Nothing to leak.
- **Debug builds are debuggable**, which is the point on a single owned device.

### Negative

- **The APK is not distributable.** Installing it requires sideloading, and a
  debug build is not what anyone else should install. **RISK-022** records this
  as accepted for a personal device, with a note to revisit before any
  third-party distribution.
- **`allowMixedContent: true` weakens the WebView's transport guarantees.** On a
  hostile network an attacker could inject content into the app's WebView. This
  is acceptable only because the device talks to the operator's own host over
  Tailscale, not over arbitrary networks.
- **No release pipeline means no version discipline.** `versionCode` is `1` and
  will stay there unless someone changes it by hand; there is no bump script and
  no tag-to-build link.
- **The APK is not exercised by CI.** No workflow builds it, so a Capacitor or
  Android toolchain break is discovered when someone next builds by hand.

## Related

- `docs/ACCEPTED_RISKS.md` **RISK-022** — the debug build and mixed content,
  accepted for a personal device.
- `mobile/capacitor.config.json`, `mobile/package.json`,
  `mobile/android/app/build.gradle` — the build definition.
- **ADR-023** — push, which is one of the capabilities the APK exists to
  support.
