# LineageOS 24.0 / Android 17 — Pixel 3 Core GApps

**Experimental branch:** `feat/blueline-core-gapps`

This is a **separate** GApps-included build of the working vanilla Pixel 3
(blueline) LineageOS 24.0 source. The original `main` local manifest and
`lineage-24.0` device branch remain unchanged.

## What's included

- Google Play Store (`Phonesky`)
- Google Play Services (original signed `PrebuiltGmsCoreVic` APK, repackaged
  as a privileged /product app)
- Google Services Framework
- Google Partner Setup
- Google contacts and calendar sync adapters
- Matching Google permissions, sysconfig and initialization metadata

**Not included:** Google Assistant/Search, Pixel Launcher, Gmail, Maps,
YouTube, Chrome, Google Setup Wizard, Android Auto, Wellbeing, TalkBack,
Speech Services, or the Google Restore app. Install optional apps from
Play Store yourself.

## Why it uses an extracted APK

MindTheGapps' Android 17 `cinnamonbun` arm64 source ships Google Play
Services inside `com.google.android.gmssystem.prodvic.apex`, whose payload is
EROFS. The Pixel 3 uses a Linux 4.9 kernel without EROFS mounting, so the
ordinary APEX cannot run even if a GApps ZIP appears to sideload correctly.

The build helper uses `fsck.erofs` on the **build host** to extract the
**same signed Google Play Services APK** and its XML declarations. It then
installs them on /product. The original APEX module is deliberately **not**
included. This follows the compatibility approach used for another legacy
4.9 Pixel port. The APK and extracted blobs are generated locally, ignored
by Git, and **not** committed or stored in the repositories.

The Google package sources come from
`MindTheGapps/vendor_gapps` (branch `cinnamonbun`).
Only selected core modules are included; we never inherit its full
`arm64-vendor.mk`.

## Fresh build on ServerHive

Use a separate checkout to retain your known-good vanilla build. On
Ubuntu, ensure that `fsck.erofs` is available (for example, from
`sudo apt-get install erofs-utils`), or provide
`GAPPS_FSCK_EROFS=/path/to/fsck.erofs`.

```bash
mkdir -p ~/lineageos-blueline-gapps
cd ~/lineageos-blueline-gapps

repo init -u https://github.com/LineageOS/android.git \
  -b lineage-24.0 --git-lfs --no-clone-bundle

git clone --branch feat/blueline-core-gapps \
  https://github.com/its-hecker/Blueline-lineagecnb-Local-Manifest.git \
  .repo/local_manifests

repo sync -c --fail-fast --no-clone-bundle --no-tags

LINEAGE_BUILD_VARIANT=userdebug \
PIXEL3_DEV_USB_ADB=true \
USE_RBE=true \
bash .repo/local_manifests/build.sh
```

The helper handles vendor blob preparation, GMS APEX extraction, the existing
kernel configuration check and `m bacon`. It has no fixed `-j` limit.
A packaged build is expected in `out/target/product/blueline/`; logs are
written to `out/build-logs/`. Building does not flash the phone.

## Existing vanilla checkout: switch only if you intend to test GApps

If you prefer to reuse an existing LineageOS checkout, make sure
`.repo/local_manifests` has no uncommitted edits before switching:

```bash
cd ~/lineageos-blueline
git -C .repo/local_manifests fetch origin feat/blueline-core-gapps
git -C .repo/local_manifests switch -c feat/blueline-core-gapps \
  --track origin/feat/blueline-core-gapps

repo sync -c --fail-fast --no-clone-bundle --no-tags

LINEAGE_BUILD_VARIANT=userdebug \
PIXEL3_DEV_USB_ADB=true \
USE_RBE=true \
bash .repo/local_manifests/build.sh
```

The new branch pins the GApps-only device-tree revision while retaining
the previous kernel and platform compatibility pins.

## Quick checks

Check sources without building:

```bash
bash .repo/local_manifests/build.sh --check
```

Prepare the vendor blobs and extract core GApps without compiling:

```bash
bash .repo/local_manifests/build.sh --prepare-only
```

After a build, verify that these are present in the output:

```bash
test -f out/target/product/blueline/product/priv-app/HeckerGmsCoreCompat/HeckerGmsCoreCompat.apk
test -f out/target/product/blueline/product/priv-app/Phonesky/Phonesky.apk
test ! -f out/target/product/blueline/product/apex/com.google.android.gmssystem.prodvic.apex
```

After flashing and booting the test ROM, verify that Android recognizes
all three packages and that Google account login and Play Store work:

```bash
adb shell pm path com.google.android.gms
adb shell pm path com.google.android.gsf
adb shell pm path com.android.vending
```

A successful build is **not** proof that Google sign-in works. Back up
important data before testing; changing between vanilla and GApps builds can
require a clean installation depending on prior Google package state.

## Source branches

- This local manifest: `feat/blueline-core-gapps`
- Device tree: `its-hecker/android_device_google_crosshatch`,
  `feat/blueline-core-gapps` (pinned in `blueline.xml`)
- Vanilla local manifest: `main`, unchanged
- Vanilla device tree: `lineage-24.0`, unchanged
- Kernel: existing pinned `lineage-24.0` Linux 4.9 kernel; no new kernel patch
- Pixel 3 vendor: existing `lineage-24.0` branch
- GApps source: `MindTheGapps/vendor_gapps`, `cinnamonbun`

Credits: LineageOS, MindTheGapps, Pixel device contributors and the
legacy-4.9 Android 17 compatibility work by xbill9.
