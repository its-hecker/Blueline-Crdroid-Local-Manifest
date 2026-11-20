#!/usr/bin/env bash
# Unofficial LineageOS 24.0 / Android 17 for Pixel 3 (blueline).
set -e -o pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
MODE=${1:-build}
case "$MODE" in
    build|--check|--prepare-only) ;;
    *) echo "Usage: bash .repo/local_manifests/build.sh [--check|--prepare-only]" >&2; exit 2 ;;
esac
if (( $# > 1 )); then
    echo "Only one mode argument is accepted." >&2
    exit 2
fi

if [[ ! -f build/envsetup.sh ]]; then
    echo "Run this command from the root of the LineageOS source checkout." >&2
    exit 1
fi
TOP=$(pwd -P)

required=(
    device/google/crosshatch/lineage_blueline.mk
    device/google/crosshatch/blueline/extract-files.py
    vendor/google/blueline/blueline-vendor.mk
    kernel/google/msm-4.9/Makefile
    kernel/google/msm-4.9/.gitmodules
    kernel/google/msm-4.9/arch/arm64/configs/b1c1_defconfig
    hardware/qcom/audio/Android.bp
    hardware/qcom/sdm845/display/Android.bp
    hardware/qcom/sdm845/gps/Android.bp
    tools/extract-utils/extract_utils/main.py
    prebuilts/extract-tools/linux-x86/bin/patchelf-0_18
    prebuilts/clang/kernel/linux-x86/clang-r416183b/bin/clang
    prebuilts/gcc/linux-x86/aarch64/aarch64-linux-android-4.9/bin/aarch64-linux-android-ld.gold
    prebuilts/gcc/linux-x86/arm/arm-linux-androideabi-4.9/bin/arm-linux-androideabi-ld
    vendor/gapps/arm64/arm64-vendor.mk
    vendor/gapps/common/common-vendor.mk
    device/google/crosshatch/blueline/gapps/core-gapps.mk
    device/google/crosshatch/blueline/gapps/Android.bp
)
missing=0
for path in "${required[@]}"; do
    if [[ ! -f "$path" ]]; then
        echo "Missing source/tool: $path" >&2
        missing=1
    fi
done
if (( missing )); then
    echo "Complete repo sync with blueline.xml before building." >&2
    exit 1
fi
if [[ -n ${LINEAGE_BUILD_JOBS:-} && ! ${LINEAGE_BUILD_JOBS} =~ ^[1-9][0-9]*$ ]]; then
    echo "LINEAGE_BUILD_JOBS must be a positive integer, or unset for default jobs." >&2
    exit 2
fi
# Preflight confirms KSU is wired into this kernel's config and source tree.
for setting in CONFIG_KSU=y CONFIG_KSU_MANUAL_HOOK=y; do
    if ! grep -Fqx "$setting" kernel/google/msm-4.9/arch/arm64/configs/b1c1_defconfig; then
        echo "KernelSU Next setting missing from b1c1_defconfig: $setting" >&2
        exit 1
    fi
done
if [[ ! -L kernel/google/msm-4.9/drivers/kernelsu ]]; then
    echo "KernelSU driver link missing (must point into the pinned submodule)" >&2
    exit 1
fi
if [[ "$MODE" == --check ]]; then
    echo "Pixel 3 source and tool paths are present. No compilation or hardware test was run."
    exit 0
fi

# Mirror the pinned KernelSU Next submodule integration from Infinity-X.
# Do not fetch a moving branch head or install SUSFS.
KSU_NEXT_PIN=23e2cb70ba728af4fb50f2203fcb34c098023188
echo "Initializing pinned KernelSU Next submodule for Pixel 3 (no SUSFS)"
git -C kernel/google/msm-4.9 submodule sync -- KernelSU
git -C kernel/google/msm-4.9 submodule update --init -- KernelSU
test -f kernel/google/msm-4.9/drivers/kernelsu/Kconfig || {
    echo "KernelSU Next driver symlink or submodule is missing" >&2
    exit 1
}
actual_ksu=$(git -C kernel/google/msm-4.9/KernelSU rev-parse HEAD)
if [[ "$actual_ksu" != "$KSU_NEXT_PIN" ]]; then
    echo "Unexpected KernelSU Next revision: $actual_ksu (expected $KSU_NEXT_PIN)" >&2
    exit 1
fi
echo "KernelSU Next pinned revision: $actual_ksu"

python3 "$SCRIPT_DIR/scripts/prepare-vendor.py" "$TOP"
# The Pixel 3 kernel cannot mount the Android 17 GMS EROFS APEX. Prepare
# its original signed APK and permission declarations before lunch/Soong.
python3 "$SCRIPT_DIR/scripts/prepare-gapps.py" "$TOP"
if [[ "$MODE" == --prepare-only ]]; then
    exit 0
fi

# Reuse ServerHive's existing RBE configuration and credentials.
export USE_RBE=true
export LINEAGE_BUILDTYPE=UNOFFICIAL
LINEAGE_BUILD_VARIANT=${LINEAGE_BUILD_VARIANT:-eng}
case "$LINEAGE_BUILD_VARIANT" in eng|userdebug) ;; *) echo "Use eng or userdebug for diagnostics" >&2; exit 2 ;; esac
mkdir -p out/build-logs
BUILD_LOG="$TOP/out/build-logs/lineage-blueline-$(date -u +%Y%m%d-%H%M%S).log"
echo "Build log: $BUILD_LOG"
(
    # Android's envsetup scripts are not compatible with nounset.
    source build/envsetup.sh
    lunch lineage_blueline cp2a "$LINEAGE_BUILD_VARIANT"
    # Validate the resolved Kconfig before compiling or packaging the kernel.
    m kernelconfig
    python3 "$SCRIPT_DIR/scripts/check-kernel-config.py" "$ANDROID_PRODUCT_OUT/obj/KERNEL_OBJ/.config"
    if [[ -n ${LINEAGE_BUILD_JOBS:-} ]]; then
        m bacon "-j${LINEAGE_BUILD_JOBS}"
    else
        # Let Android choose its default parallelism; no fixed -j8 cap.
        m bacon
    fi

) 2>&1 | tee "$BUILD_LOG"
