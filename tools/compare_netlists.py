#!/usr/bin/env python3
"""Compare the reviewed Calxus logical pin-net map with a real EDA export.

Accepted actual inputs: CSV ref,pin,net; KiCad XML; JSON nets[{name,nodes:[{ref,pin}]}];
JSON components/parts[{ref,pins:{pin:net}}]; native JLCEDA components{props.Designator,
pinInfoMap{number,net}}. Unknown formats fail, never pass by guessing.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict


def field(row: dict, *names: str):
    low = {str(k).lower(): v for k, v in row.items()}
    for name in names:
        if name.lower() in low:
            return low[name.lower()]
    return None


def empty_net(value):
    return value is None or str(value).strip() in ("", "None", "null")


def read_actual(path: Path) -> list[tuple[str, str, str | None]]:
    raw = path.read_text(encoding="utf-8-sig")
    if path.suffix.lower() == ".csv":
        rows = list(csv.DictReader(raw.splitlines()))
        answer = []
        for row in rows:
            ref, pin, net = field(row, "ref", "reference", "designator"), field(row, "pin", "pinnumber"), field(row, "net", "netname")
            if ref is None or pin is None:
                raise ValueError("CSV needs ref,pin,net columns")
            answer.append((str(ref), str(pin), None if empty_net(net) else str(net)))
        return answer
    if raw.lstrip().startswith("<"):
        root = ET.fromstring(raw)
        answer = []
        for net in root.findall(".//nets/net"):
            name = net.get("name")
            for node in net.findall("node"):
                if node.get("ref") is None or node.get("pin") is None:
                    raise ValueError("XML net node lacks ref/pin")
                answer.append((node.get("ref"), node.get("pin"), name))
        if not answer:
            raise ValueError("No KiCad XML net nodes found")
        return answer
    data = json.loads(raw)
    if isinstance(data, dict) and isinstance(data.get("netlist"), dict):
        data = data["netlist"]
    if not isinstance(data, dict):
        raise ValueError("JSON actual netlist must be an object")
    if isinstance(data.get("nets"), list):
        answer = []
        for net in data["nets"]:
            name = field(net, "name", "net", "netName")
            nodes = field(net, "nodes", "pins")
            if not isinstance(nodes, list):
                raise ValueError("Each JSON net needs nodes/pins array")
            for node in nodes:
                ref, pin = field(node, "ref", "reference", "designator"), field(node, "pin", "pinNumber")
                if ref is None or pin is None:
                    raise ValueError("JSON net node lacks ref/pin; normalize by actual pinNumber first")
                answer.append((str(ref), str(pin), None if empty_net(name) else str(name)))
        return answer
    components = data.get("components", data.get("parts"))
    if isinstance(components, dict):
        # Observed native JLCEDA export. Keys are component/pin UUIDs; physical
        # numbering must come from number, not the dictionary key or pin name.
        answer, seen = [], set()
        for part in components.values():
            ref = part.get("props", {}).get("Designator")
            pin_map = part.get("pinInfoMap")
            if not ref or not isinstance(pin_map, dict) or not pin_map:
                raise ValueError("Native JLCEDA component requires props.Designator and nonempty pinInfoMap")
            if ref in seen:
                raise ValueError(f"Duplicate native JLCEDA component Designator {ref}")
            seen.add(ref)
            for pin in pin_map.values():
                if "number" not in pin or "net" not in pin:
                    raise ValueError(f"Native JLCEDA {ref} pin requires number and net")
                answer.append((str(ref), str(pin["number"]), None if empty_net(pin["net"]) else str(pin["net"])))
        return answer
    if isinstance(components, list):
        answer = []
        for part in components:
            ref = field(part, "ref", "reference", "designator")
            pins = part.get("pins")
            if ref is None or not isinstance(pins, dict):
                raise ValueError("JSON component needs ref and pins object")
            for pin, net in pins.items():
                if isinstance(net, dict):
                    net = field(net, "net", "netName")
                answer.append((str(ref), str(pin), None if empty_net(net) else str(net)))
        return answer
    raise ValueError("Unrecognized actual netlist format; export/normalize actual ref,pinNumber,netName explicitly")


def make_aliases(parts: list[dict], extra: dict | None = None) -> dict[tuple[str, str], str]:
    aliases = {}
    for part in parts:
        ref = part["ref"]
        model = str(part.get("mpn", part.get("value", "")))
        mapping = {}
        if "TUSB3410" in model:
            mapping = {"EP": "33"}
        elif model == "CH343P":
            # EDA library geometry verified in this project: datasheet 0 is pad 17.
            mapping = {"0": "17", "EP": "17"}
        elif "TYPE-C-31-M-12" in model:
            mapping = {"A1": "A1B12", "B12": "A1B12", "A4": "A4B9", "B9": "A4B9",
                       "B4": "B4A9", "A9": "B4A9", "B1": "B1A12", "A12": "B1A12",
                       "S1": "1", "S2": "2", "S3": "3", "S4": "4"}
        if ref == "J2":
            mapping["SH"] = "5"
        aliases.update({(ref, str(old)): str(new) for old, new in mapping.items()})
    for ref, mapping in (extra or {}).items():
        aliases.update({(ref, str(old)): str(new) for old, new in mapping.items()})
    return aliases


def canonical(rows, aliases):
    result = {}
    for ref, pin, net in rows:
        key = (ref, aliases.get((ref, str(pin)), str(pin)))
        net = None if empty_net(net) else str(net)
        if key in result and result[key] != net:
            raise ValueError(f"Conflicting merged pin {key}: {result[key]} versus {net}")
        result[key] = net
    return result


def compare(expected, actual, topology_only=False):
    errors, notes = [], []
    egroups, agroups = defaultdict(set), defaultdict(set)
    for pin, net in expected.items():
        if net is not None:
            egroups[net].add(pin)
    for pin, net in actual.items():
        if net is not None:
            agroups[net].add(pin)
    for pin, net in expected.items():
        if net is None:
            if pin in actual and actual[pin] is not None and len(agroups[actual[pin]]) > 1:
                errors.append(f"NC pin {pin[0]}.{pin[1]} is connected to {actual[pin]}")
            continue
        if pin not in actual or actual[pin] is None:
            errors.append(f"Missing connected pin {pin[0]}.{pin[1]} expected {net}")
            continue
        observed = actual[pin]
        if not topology_only and observed != net:
            errors.append(f"Net name mismatch {pin[0]}.{pin[1]}: expected {net}, actual {observed}")
    # Compare full pin groups too: a matching label on one pin cannot hide an open
    # connection or an unintended merge elsewhere.
    seen = set()
    known = set(expected)
    for pin, net in expected.items():
        if net is None or pin not in actual or actual[pin] is None:
            continue
        pair = (net, actual[pin])
        if pair in seen:
            continue
        seen.add(pair)
        observed_group = agroups[actual[pin]] & known
        if egroups[net] != observed_group:
            missing = sorted(egroups[net] - observed_group)
            extra = sorted(observed_group - egroups[net])
            errors.append(f"Connectivity mismatch net {net}: missing={missing}, extra={extra}")
    extras = sorted(set(actual) - known)
    if extras:
        errors.append(f"Unexpected actual component pins: {extras}")
    for net, group in sorted(egroups.items()):
        if len(group) == 1:
            notes.append(f"Singleton logical net {net}: {sorted(group)}; verify intentional test point/NC treatment")
    return errors, notes


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--design", type=Path, required=True)
    parser.add_argument("--actual", type=Path, required=True)
    parser.add_argument("--aliases", type=Path, help="Extra explicit {ref:{oldPin:newPin}} mapping, if actual geometry proves it")
    parser.add_argument("--scope", choices=("schematic", "pcb"), default="schematic", help="schematic excludes explicitly pcb_only pads; pcb includes all design pins")
    parser.add_argument("--topology-only", action="store_true", help="Ignore net labels but still compare complete pin groups")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        design = json.loads(args.design.read_text())
        all_parts = design["parts"]
        excluded = [p["ref"] for p in all_parts if args.scope == "schematic" and p.get("pcb_only")]
        parts = [p for p in all_parts if p["ref"] not in excluded]
        if len({p["ref"] for p in parts}) != len(parts):
            raise ValueError("Duplicate reference designators in design input")
        extra = json.loads(args.aliases.read_text()) if args.aliases else None
        aliases = make_aliases(parts, extra)
        expected = canonical([(p["ref"], pin, net) for p in parts for pin, net in p["pins"].items()], aliases)
        actual = canonical(read_actual(args.actual), aliases)
        errors, notes = compare(expected, actual, args.topology_only)
        if args.scope == "schematic":
            notes = [n + " (PCB-only test pads are explicitly excluded in this scope.)" for n in notes]
        report = {"pass": not errors, "design_sha256": hashlib.sha256(args.design.read_bytes()).hexdigest(),
                  "actual_sha256": hashlib.sha256(args.actual.read_bytes()).hexdigest(),
                  "expected_components": len(parts), "actual_components": len({ref for ref,pin in actual}),
                  "expected_pins": len(expected), "actual_pins": len(actual),
                  "comparison_scope": args.scope, "excluded_pcb_only_refs": excluded,
                  "alias_basis": "Verified project library: TUSB EP33, CH343 EP17, grouped USB-C pins, USB-A shield5",
                  "errors": errors, "notes": notes,
                  "scope": "Pin-net export equivalence only for the stated schematic/PCB scope; does not verify routed copper, firmware, power timing or hardware behavior"}
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if not errors else 1
    except (OSError, ValueError, KeyError, ET.ParseError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
