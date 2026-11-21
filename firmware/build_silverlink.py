#!/usr/bin/env python3
"""Build the pinned SilverLink reference and prepare exact programming images.

This build helper is original Calxus code. Upstream source and reconstructed
firmware are fetched/built locally and are not relicensed by this helper.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import urllib.request
from datetime import datetime, timezone

COMMIT = "f0db48b761ca64f77ad3d27dd3d0a98930638d04"
BASE = f"https://raw.githubusercontent.com/queueRAM/ti_graph_link/{COMMIT}/"
SOURCES = {
    "Makefile": "c21c205db27064c1b2a2621aad6c2ed8a3940b65b49c8e431556c0da0f300bf0",
    "ti_graph_link_silver.asm": "275dac5460b4af4bb975cb422e10cbd505ab69a68a166bc17c5329c4660168a1",
    "ti_graph_link_silver.sha1": "e353325e1083387e31bd333a30b7be94bae12ad3eecaf63a2e5349ed79150ced",
    "tools/generate_eeprom.py": "0f1476a2528bcf0eb655f190b89e52a01fd3ab8fea1fe934cbc48c91e79ec341",
}
REFERENCE_SHA1 = "6255d46f667840cccdf46e94fa7a462330076a0b"
REFERENCE_SHA256 = "3227e2eb733c93737c05fbf556e52afab8048e9719be72286c2d50bc0539916f"


def digest(data: bytes, algorithm: str = "sha256") -> str:
    return hashlib.new(algorithm, data).hexdigest()


def run(argv: list[str], directory: Path, log: list[str]) -> str:
    log.append("$ " + " ".join(argv))
    result = subprocess.run(argv, cwd=directory, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    log.append(result.stdout.rstrip())
    if result.returncode:
        raise RuntimeError(f"Command failed ({result.returncode}): {' '.join(argv)}\n{result.stdout}")
    return result.stdout


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path,
                        help="Use an existing exact upstream checkout instead of downloading")
    parser.add_argument("--output", type=Path, default=Path("build/silverlink"))
    args = parser.parse_args()
    for tool in ("sdas8051", "sdcc", "makebin"):
        if shutil.which(tool) is None:
            parser.error(f"Missing {tool}; install SDCC 4.2.0 (or a compatible version) first")
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    log: list[str] = []
    try:
        with tempfile.TemporaryDirectory(prefix="calxus-silverlink-") as temp:
            work = Path(temp)
            for name, expected in SOURCES.items():
                if args.source_dir:
                    data = (args.source_dir / name).read_bytes()
                else:
                    request = urllib.request.Request(BASE + name, headers={"User-Agent": "Calxus-build/1"})
                    with urllib.request.urlopen(request, timeout=30) as response:
                        data = response.read()
                if digest(data) != expected:
                    raise ValueError(f"Upstream source hash mismatch: {name}")
                target = work / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
            version = run(["sdcc", "--version"], work, log).splitlines()[0]
            run(["sdas8051", "-lops", "ti_graph_link_silver.asm"], work, log)
            run(["sdcc", "-mmcs51", "--code-size", "0x1400",
                 "ti_graph_link_silver.rel", "-o", "ti_graph_link_silver.hex"], work, log)
            run(["makebin", "-p", "ti_graph_link_silver.hex", "ti_graph_link_silver.bin"], work, log)
            run([sys.executable, "tools/generate_eeprom.py", "ti_graph_link_silver.bin",
                 "ti_graph_link_silver.eep"], work, log)
            code = (work / "ti_graph_link_silver.bin").read_bytes()
            if len(code) != 0x1400 or digest(code, "sha1") != REFERENCE_SHA1 or digest(code) != REFERENCE_SHA256:
                raise ValueError("Build differs from the pinned 5120-byte reference; no programming images emitted")
            checksum = sum(code) & 0xFF
            raw_eep = (work / "ti_graph_link_silver.eep").read_bytes()
            expected_eep = struct.pack("<HBHB", 0x3410, 7, len(code), checksum) + code
            if raw_eep != expected_eep:
                raise ValueError("Unexpected upstream EEPROM wrapper")
            # The upstream wrapper has no terminating descriptor byte. Add an
            # explicit terminator, then FF-fill the remainder of the 24LC64.
            complete = raw_eep + b"\x00"
            complete += b"\xff" * (8192 - len(complete))
            usb_ram = struct.pack("<HB", len(code), checksum) + code
            artifacts = {
                "ti_graph_link_silver.bin": code,
                "ti_graph_link_silver.hex": (work / "ti_graph_link_silver.hex").read_bytes(),
                "ti_graph_link_silver.eep": raw_eep,
                "calxus_silverlink_24lc64.bin": complete,
                "calxus_silverlink_usb_ram.bin": usb_ram,
            }
            record = {
                "schema": 1, "built_at_utc": datetime.now(timezone.utc).isoformat(),
                "upstream": "https://github.com/queueRAM/ti_graph_link",
                "commit": COMMIT, "toolchain": version,
                "source_sha256": SOURCES,
                "upstream_license_observed": "No LICENSE/COPYING at pinned commit; ASM identifies itself as disassembly",
                "binary_sha1": digest(code, "sha1"), "checksum_u8": checksum,
                "hardware_tested": False,
                "artifacts": {name: {"bytes": len(data), "sha256": digest(data)} for name, data in artifacts.items()},
            }
            for name, data in artifacts.items():
                (output / name).write_bytes(data)
            (output / "BUILD_RECORD.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            log.append("PASS: upstream SHA1 and SHA256 match; EEPROM header/checksum/terminator constructed.")
            (output / "build.log").write_text("\n".join(log) + "\n", encoding="utf-8")
            print(json.dumps(record, ensure_ascii=False, indent=2))
    except (OSError, ValueError, RuntimeError) as error:
        (output / "build-failure.log").write_text("\n".join(log) + "\n" + str(error) + "\n", encoding="utf-8")
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
