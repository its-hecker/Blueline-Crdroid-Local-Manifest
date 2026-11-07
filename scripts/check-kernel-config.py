#!/usr/bin/env python3
"""Reject Pixel 3 kernel configurations that cannot start Android recovery."""

import argparse
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path, help="Generated KERNEL_OBJ/.config")
    args = parser.parse_args()
    try:
        lines = args.config.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as error:
        print(f"Cannot read generated kernel config: {error}", file=sys.stderr)
        return 2

    values = dict(line.split("=", 1) for line in lines if line.startswith("CONFIG_") and "=" in line)
    required = {
        "CONFIG_BOARD_B1C1": "y",
        "CONFIG_SECURITY": "y",
        "CONFIG_SECURITY_NETWORK": "y",
        "CONFIG_SECURITY_SELINUX": "y",
        "CONFIG_DEFAULT_SECURITY_SELINUX": "y",
        "CONFIG_DEFAULT_SECURITY": '"selinux"',
    }
    missing = [f"{name}={value}" for name, value in required.items() if values.get(name) != value]
    if missing:
        print("Pixel 3 kernel cannot start Android recovery. Required settings:", file=sys.stderr)
        for setting in missing:
            print(f"  {setting}", file=sys.stderr)
        print(
            "Sync the fixed b1c1_defconfig and regenerate the kernel config. "
            "SELinux needs SECURITY_NETWORK even with Smack disabled.",
            file=sys.stderr,
        )
        return 1

    print("Pixel 3 generated kernel config: SELinux and its networking hooks are enabled.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
