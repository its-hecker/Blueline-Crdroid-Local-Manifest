#!/usr/bin/env python3
"""Apply the device tree's existing ELF fixups and regenerate vendor makefiles.

No phone or factory-image download is needed: the input is the synced vendor
repository. Fixups are staged before replacing any blob and can be run again.
"""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


def prepare(top: Path) -> None:
    top = top.resolve()
    vendor = top / "vendor/google/blueline/proprietary"
    extractor = top / "device/google/crosshatch/blueline/extract-files.py"
    extract_utils = top / "tools/extract-utils"
    patchelf = top / "prebuilts/extract-tools/linux-x86/bin/patchelf-0_18"
    for required in (vendor, extractor, extract_utils / "extract_utils/main.py", patchelf):
        if not required.exists():
            raise RuntimeError(f"Missing {required}; complete repo sync first")
    if not os.access(patchelf, os.X_OK):
        raise RuntimeError(f"Not executable: {patchelf}")

    sys.path.insert(0, str(extract_utils))
    from extract_utils.file import File
    from extract_utils.fixups_blob import BlobFixupCtx

    spec = importlib.util.spec_from_file_location("blueline_blob_fixups", extractor)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load the device extractor: {extractor}")
    device = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(device)

    # Use the device's extraction recipe rather than maintaining another list
    # of camera, fingerprint, Citadel and Secure UI transformations here.
    recipes = {}
    for paths, fixup in device.blob_fixups.items():
        for relative in (paths,) if isinstance(paths, str) else paths:
            if relative in recipes:
                raise RuntimeError(f"Duplicate blob fixup: {relative}")
            recipes[relative] = fixup

    for relative in recipes:
        target = vendor / relative
        if not target.resolve().is_relative_to(vendor.resolve()):
            raise RuntimeError(f"Blob path escapes the vendor directory: {relative}")
        if not target.is_file():
            raise RuntimeError(f"Missing vendor blob: {relative}")
        with target.open("rb") as stream:
            magic = stream.read(4)
        if magic != b"\x7fELF":
            raise RuntimeError(f"Expected an ELF blob, found a pointer or other data: {relative}")

    context = BlobFixupCtx(str(extractor.parent))
    changed = []
    with tempfile.TemporaryDirectory(prefix=".lineage24-fixups-", dir=vendor.parent) as tmp:
        staged_root = Path(tmp)
        for relative, fixup in recipes.items():
            original = vendor / relative
            staged = staged_root / relative
            staged.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(original, staged)
            if not fixup.run(context, File(relative), str(staged)):
                raise RuntimeError(f"Vendor fixup failed: {relative}")
            if staged.read_bytes() != original.read_bytes():
                changed.append((staged, original))
        for staged, original in changed:
            os.replace(staged, original)
            print(f"Patched {original.relative_to(vendor)}", flush=True)

    # -m regenerates build definitions from the patched local ELFs. It skips
    # source extraction entirely, so it never falls back to ADB.
    env = os.environ.copy()
    env["PYTHONPATH"] = str(extract_utils) + (
        os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else ""
    )
    subprocess.run([sys.executable, str(extractor), "-m"], cwd=top, env=env, check=True)
    print(f"Vendor preparation complete: {len(changed)} blobs changed; makefiles regenerated.")


def main() -> int:
    if len(sys.argv) > 2:
        print("Usage: prepare-vendor.py [LineageOS source root]", file=sys.stderr)
        return 2
    try:
        prepare(Path(sys.argv[1]) if len(sys.argv) == 2 else Path.cwd())
    except (OSError, RuntimeError, ImportError, subprocess.CalledProcessError) as error:
        print(f"Vendor preparation failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
