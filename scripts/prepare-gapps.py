#!/usr/bin/env python3
"""Prepare minimal Android 17 GApps for the Pixel 3's Linux 4.9 kernel.

MindTheGapps cinnamonbun ships Google Play Services inside an EROFS APEX.
The Pixel 3 kernel cannot mount EROFS, so unpack the original signed APK and
the APEX's permission/sysconfig declarations into the *local source checkout*.
No proprietary APKs are ever committed to the device or manifest repositories.

Requires fsck.erofs (erofs-utils) on PATH or in out/host/linux-x86/bin.
"""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import zipfile


GAPPS_APEX = "com.google.android.gmssystem.prodvic.apex"
DEST = Path("device/google/crosshatch/blueline/gapps/generated")


def find_fsck(top: Path) -> str:
    override = os.environ.get("GAPPS_FSCK_EROFS")
    candidates = [
        override,
        str(top / "out/host/linux-x86/bin/fsck.erofs"),
        shutil.which("fsck.erofs"),
    ]
    for candidate in candidates:
        if candidate and Path(candidate).is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    raise RuntimeError(
        "fsck.erofs not found. Install erofs-utils on the build server, "
        "or set GAPPS_FSCK_EROFS to the host tool's path."
    )


def apex_pieces(top: Path) -> list[Path]:
    apex_dir = top / "vendor/gapps/arm64/proprietary/product/apex"
    single = apex_dir / GAPPS_APEX
    if single.is_file():
        return [single]
    pieces = sorted(apex_dir.glob(GAPPS_APEX + ".[0-9][0-9]"))
    if not pieces or pieces[0].suffix != ".00":
        raise RuntimeError(
            "Missing MindTheGapps Android 17 arm64 GMS APEX split files in "
            + str(apex_dir)
            + ". Check that vendor/gapps synced successfully."
        )
    if [int(p.suffix[1:]) for p in pieces] != list(range(len(pieces))):
        raise RuntimeError("GMS APEX chunks are incomplete or out of sequence")
    return pieces


def prepare(top: Path) -> None:
    top = top.resolve()
    dest = top / DEST
    bp = dest.parent / "Android.bp"
    if not bp.is_file():
        raise RuntimeError("Device tree is not the core-GApps branch: " + str(bp))
    pieces = apex_pieces(top)
    fsck = find_fsck(top)

    with tempfile.TemporaryDirectory(prefix="blueline-gms-") as work:
        temp = Path(work)
        apex = temp / GAPPS_APEX
        with apex.open("wb") as output:
            for piece in pieces:
                with piece.open("rb") as stream:
                    shutil.copyfileobj(stream, output, length=1024 * 1024)

        if not zipfile.is_zipfile(apex):
            raise RuntimeError(
                "GMS APEX is not a valid ZIP. Check for missing blobs/LFS pointers."
            )
        image = temp / "apex_payload.img"
        with zipfile.ZipFile(apex) as zf:
            if "apex_payload.img" not in zf.namelist():
                raise RuntimeError("GMS APEX is missing apex_payload.img")
            with zf.open("apex_payload.img") as source, image.open("wb") as target:
                shutil.copyfileobj(source, target, length=1024 * 1024)

        payload = temp / "payload"
        payload.mkdir()
        subprocess.run([fsck, "--extract=" + str(payload), str(image)], check=True)

        apks = sorted((payload / "priv-app").glob("*/*.apk"))
        if len(apks) != 1:
            raise RuntimeError(
                "Expected exactly one GMS APK inside the APEX; found: "
                + ", ".join(str(p) for p in apks)
            )
        apk = apks[0]
        with zipfile.ZipFile(apk) as zf:
            if "AndroidManifest.xml" not in zf.namelist():
                raise RuntimeError("Extracted Play Services APK is invalid")

        staged = temp / "generated"
        staged.mkdir()
        shutil.copy2(apk, staged / "PrebuiltGmsCoreVic.apk")

        # Keep the matching permissions from the same GMS version. These are
        # required for privileged Google Play Services outside an APEX.
        entries = []
        for folder in ("permissions", "sysconfig"):
            source_root = payload / "etc" / folder
            if not source_root.is_dir():
                raise RuntimeError("GMS payload missing /etc/" + folder)
            files = sorted(p for p in source_root.rglob("*") if p.is_file())
            if not files:
                raise RuntimeError("GMS payload has empty /etc/" + folder)
            for source in files:
                relative = source.relative_to(payload / "etc")
                if source.suffix != ".xml":
                    raise RuntimeError("Unexpected non-XML GMS permission file: " + str(relative))
                target = staged / "etc" / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
                src = str(DEST / "etc" / relative)
                dst = "$(TARGET_COPY_OUT_PRODUCT)/etc/" + relative.as_posix()
                entries.append((src, dst))

        mk = staged / "gms-permissions.mk"
        with mk.open("w", encoding="utf-8") as f:
            f.write("# Generated from the MindTheGapps GMS APEX; do not edit.\n")
            f.write("PRODUCT_COPY_FILES += \\\n")
            for idx, (source, target) in enumerate(entries):
                end = " \\" if idx != len(entries) - 1 else ""
                f.write("    " + source + ":" + target + end + "\n")

        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(staged, dest)
        print(
            "Prepared Play Services APK ("
            + str((dest / "PrebuiltGmsCoreVic.apk").stat().st_size)
            + " bytes) and "
            + str(len(entries))
            + " permission/sysconfig files for legacy Pixel 3 kernel."
        )


if __name__ == "__main__":
    try:
        if len(sys.argv) > 2:
            raise RuntimeError("Usage: prepare-gapps.py [Android source root]")
        prepare(Path(sys.argv[1]) if len(sys.argv) == 2 else Path.cwd())
    except (RuntimeError, OSError, ValueError, zipfile.BadZipFile, subprocess.CalledProcessError) as error:
        print("Core GApps preparation failed: " + str(error), file=sys.stderr)
        sys.exit(1)
