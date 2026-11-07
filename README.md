# LineageOS 24.0 / Android 17 — Pixel 3 (blueline)

Unofficial, vanilla Android 17 development target for **Google Pixel 3**.
The existing repository URL retains its old crDroid name; its `main` branch now
contains the LineageOS configuration.

**Status:** a full ROM build is available, but the 4 November image hangs before
recovery. Inspection confirmed that its compiled kernel lacks SELinux. The
recovery fix below restores the missing dependency; a rebuilt image and a
successful phone boot still need verification. The Pixel 3 remains officially on
LineageOS 22.2; this is an independent port.

## Fresh build from mkdir — default jobs, RBE enabled

Use a new source directory to avoid mixing a crDroid source checkout with
LineageOS. On ServerHive, use its existing Android build dependencies and RBE
configuration. Install Git LFS before syncing; the vendor radio images use it.

```bash
mkdir -p ~/lineageos-blueline &&
cd ~/lineageos-blueline &&
repo init -u https://github.com/LineageOS/android.git -b lineage-24.0 --git-lfs --no-clone-bundle &&
git clone --branch main https://github.com/its-hecker/Blueline-Crdroid-Local-Manifest.git .repo/local_manifests &&
repo sync -c --fail-fast --no-clone-bundle --no-tags &&
env -u HECKER_BUILD_JOBS -u BUILD_JOBS -u LINEAGE_BUILD_JOBS USE_RBE=true bash .repo/local_manifests/build.sh
```

The default command passes **no fixed job count** to Android's build system.
It does not use `-j8`. `USE_RBE=true` reuses the server's RBE setup; this
repository does not create credentials or configure an RBE service.

## Subsequent builds

From `~/lineageos-blueline`:

```bash
git -C .repo/local_manifests pull --ff-only origin main &&
repo sync -c --fail-fast --no-clone-bundle --no-tags &&
env -u HECKER_BUILD_JOBS -u BUILD_JOBS -u LINEAGE_BUILD_JOBS USE_RBE=true bash .repo/local_manifests/build.sh
```

The helper checks source/tool paths, prepares vendor blobs, runs
`lunch lineage_blueline cp2a userdebug`, and builds with `m bacon`.
Build output is in `out/target/product/blueline/`; logs are in `out/build-logs/`.
It never flashes a connected phone.

For a source/tool presence check only:

```bash
bash .repo/local_manifests/build.sh --check
```

To prepare the vendor files without starting a build:

```bash
bash .repo/local_manifests/build.sh --prepare-only
```

## Recovery fix — 8 November 2026

The 4 November boot image matches ServerHive's published checksum but its
embedded kernel configuration has no SELinux support. Disabling the unused
Smack LSM also removed its implicit selection of `SECURITY_NETWORK`, a dependency
of SELinux. Kconfig silently dropped `SECURITY_SELINUX=y`, so init cannot mount
selinuxfs and start recovery.

The kernel's `lineage-24.0` branch now selects `SECURITY_NETWORK` and the SELinux
default explicitly. The build helper runs `m kernelconfig` and checks the
generated configuration before compiling the ROM.

For the first rebuild after this fix, clear only the generated kernel and
device-tree outputs, then build the complete package so its kernel modules match:

```bash
cd ~/lineageos-blueline &&
git -C .repo/local_manifests pull --ff-only origin main &&
repo sync -c --fail-fast --no-clone-bundle --no-tags &&
rm -rf out/target/product/blueline/obj/KERNEL_OBJ out/target/product/blueline/obj/DTB_OBJ out/target/product/blueline/obj/DTBO_OBJ &&
rm -f out/target/product/blueline/kernel out/target/product/blueline/boot.img out/target/product/blueline/dtb.img out/target/product/blueline/dtbo.img &&
env -u HECKER_BUILD_JOBS -u BUILD_JOBS -u LINEAGE_BUILD_JOBS PIXEL3_DEV_USB_ADB=true USE_RBE=true bash .repo/local_manifests/build.sh
```

Use the newly produced `boot.img` from `out/target/product/blueline/`; the
4 November download is still the old image. In bootloader mode, flash that new
image with `fastboot flash boot boot.img`, then select **Recovery Mode**.
A source/configuration check is not a successful phone boot test.

## Explicit 8-job command

This optional command uses **8 jobs**, and should only be used on a server
where that job setting is allowed. Use the default command on ServerHive.

```bash
USE_RBE=true LINEAGE_BUILD_JOBS=8 bash .repo/local_manifests/build.sh
```

## Sources and compatibility

| Purpose | Repository | Revision |
| --- | --- | --- |
| Android platform | `LineageOS/android` | `lineage-24.0` |
| Pixel 3 device and shared configuration | `its-hecker/android_device_google_crosshatch` | `lineage-24.0` |
| Pixel 3 vendor blobs | `its-hecker/proprietary_vendor_google_blueline` | `lineage-24.0` |
| Linux 4.9 with eBPF backports | `its-hecker/android_kernel_google_msm-4.9` | `lineage-24.0` |
| Active Edge service | `LineageOS/android_packages_apps_ElmyraService` | `lineage-24.0` |
| Legacy SDM845 display | `xbill9/android_hardware_qcom_sdm845_display` | pinned Android 17 commit |
| Legacy SDM845 GPS | `LineageOS/android_hardware_qcom_sdm845_gps` | pinned `lineage-23.2` commit |
| Legacy Qualcomm audio | `xbill9/android_hardware_qcom_audio` | pinned `lineage-23.2` commit |
| Legacy kernel binutils | LineageOS GCC 4.9 prebuilt repositories | pinned `lineage-19.1` commits |
| fscrypt, BPF, connectivity and app zygote compatibility | xbill9 platform forks | pinned Android 17 commits |

`blueline.xml` contains the exact compatibility commit pins. LineageOS supplies
kernel clang r416183b itself. Its normal Rust and host-clang projects are retained
in the source manifest.

The `crosshatch` repository is shared by Pixel 3 and Pixel 3 XL and already
defines `lineage_blueline`. This manifest uses the Pixel 3 vendor only. It does
not sync Pixel 3a/bonito device configurations or use Pixel 4 device/kernel sources.

The dedicated LineageOS device and kernel branches preserve the Android 17 work
from the earlier `crdroid-17.0` branches. The vendor branch starts from the existing
Pixel 3 blobs on `lineage-22.2`; `scripts/prepare-vendor.py` applies the device
tree's extraction fixups locally, then regenerates vendor build definitions.
This includes camera XML-library compatibility, fingerprint stats-interface
names and the Secure UI shim. Running the helper again is supported. These
generated changes will appear in the vendor checkout's Git status; keep any
personal vendor edits committed separately before updating source branches.

The initial target has no bundled GApps, keeps the existing physical partition
sizes and ext4 retrofit layout, and retains encryption, thermal protection and
SELinux enforcing from the device preparation. Android 17 kernel-version OTA
checks are disabled for the backported 4.9 kernel; HAL compatibility checking
is retained. These settings still require build and phone validation.

## First device validation

After a successful server build, test boot and SELinux state, calls and mobile
data, Wi-Fi and Bluetooth, both cameras, fingerprint, encryption/unlock,
charging/temperature and suspend. A successful source check or ZIP build alone
does not establish that these work on Pixel 3.

## Credits

LineageOS and the Pixel device maintainers provide the base device and vendor
sources. xbill9's Android 17 work on the related Pixel 3a family supplies the
legacy-kernel platform compatibility approach and shared Qualcomm components.
Their Pixel 3a boot results are not Pixel 3 validation.
