#!/usr/bin/env python3
"""Validate a complete Calxus 24LC64 image and optional programmer readback."""
from __future__ import annotations
import argparse
import hashlib
from pathlib import Path
import struct
import sys

REFERENCE_SHA256 = "3227e2eb733c93737c05fbf556e52afab8048e9719be72286c2d50bc0539916f"


def inspect(data: bytes, allow_custom: bool = False) -> dict:
    if len(data) != 8192:
        raise ValueError(f"24LC64 image must be exactly 8192 bytes; got {len(data)}")
    signature, kind, length, checksum = struct.unpack("<HBHB", data[:6])
    if signature != 0x3410 or kind != 7:
        raise ValueError("Expected TUSB3410 signature 10 34 and Autoexec type 07")
    if not (1 <= length <= 8185):
        raise ValueError(f"Invalid application length: {length}")
    code = data[6:6 + length]
    if sum(code) & 0xFF != checksum:
        raise ValueError("Application checksum mismatch")
    if data[6 + length] != 0:
        raise ValueError("Missing explicit end-of-header byte")
    if any(value != 0xFF for value in data[7 + length:]):
        raise ValueError("Unused EEPROM bytes must be FF in this canonical image")
    code_sha256 = hashlib.sha256(code).hexdigest()
    if not allow_custom and code_sha256 != REFERENCE_SHA256:
        raise ValueError("Code differs from pinned SilverLink reference; use --allow-custom only for intentional new firmware")
    return {"image_bytes": len(data), "code_bytes": length, "checksum": f"0x{checksum:02x}",
            "code_sha256": code_sha256, "image_sha256": hashlib.sha256(data).hexdigest()}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    parser.add_argument("--readback", type=Path, help="Require exact byte equality with programmer readback")
    parser.add_argument("--allow-custom", action="store_true")
    args = parser.parse_args()
    try:
        data = args.image.read_bytes()
        result = inspect(data, args.allow_custom)
        if args.readback:
            actual = args.readback.read_bytes()
            if actual != data:
                first = next((i for i, (a, b) in enumerate(zip(data, actual)) if a != b), min(len(data), len(actual)))
                raise ValueError(f"Readback differs at offset 0x{first:04x}; expected {len(data)} bytes, read {len(actual)}")
        for key, value in result.items():
            print(f"{key}: {value}")
        print("PASS: image structure" + (" and exact EEPROM readback" if args.readback else " (no hardware readback supplied)"))
    except (OSError, ValueError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
