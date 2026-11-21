#!/usr/bin/env python3
"""Independent Calxus A0 logical checks, using documented manufacturer pin roles.

This checks the design input, not exported EDA copper or analogue behavior. The
selector model derives the result from SW1 contacts and diode orientation; it
does not merely repeat the input's mode annotations. No third-party dependencies.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path


def audit(design):
    parts = {p["ref"]: p for p in design["parts"]}
    checks, errors = [], []

    def check(name, condition, observed=None):
        record = {"check": name, "pass": bool(condition)}
        if observed is not None:
            record["observed"] = observed
        checks.append(record)
        if not condition:
            errors.append(name)

    def pins(ref, expected):
        actual = parts.get(ref, {}).get("pins", {})
        for pin, net in expected.items():
            check(f"{ref}.{pin} = {net}", str(pin) in actual and actual[str(pin)] == net, actual.get(str(pin)))

    def two(ref, a, b, value=None):
        actual = parts.get(ref, {})
        check(f"{ref} joins {a} / {b}", sorted(str(n) for n in actual.get("pins", {}).values()) == sorted((a, b)))
        if value:
            check(f"{ref} value {value}", actual.get("value", "").split()[0] == value, actual.get("value"))

    # The diode graph below is valid only for these actual pin-role variants.
    for ref, model in [("D11","BAT54C-7-F"),("D14","BAT54A-7-F"),
                       *((f"D{i}","BAT54WS-7-F") for i in (8,9,10,12,13,15,16))]:
        check(f"{ref} polarity variant {model}", parts.get(ref,{}).get("mpn") == model)

    check("Unique component references", len(parts) == len(design["parts"]))
    groups = defaultdict(list)
    for ref, part in parts.items():
        for pin, net in part["pins"].items():
            if net is not None:
                groups[net].append(f"{ref}.{pin}")
    singletons = {net: nodes for net, nodes in groups.items() if len(nodes) == 1}
    check("No unintended named singleton networks", not singletons, singletons)

    # Connector numbers come from actual JLCEDA library geometry. Duplicate C
    # connector contacts must share a net; shield contacts are explicit too.
    pins("J1", {"A1B12":"GND", "B1A12":"GND", "A4B9":"VBUS_IN", "B4A9":"VBUS_IN",
                "A6":"USB_UP_DP", "B6":"USB_UP_DP", "A7":"USB_UP_DM", "B7":"USB_UP_DM",
                "A5":"CC1", "B5":"CC2", "A8":None, "B8":None,
                "1":"GND", "2":"GND", "3":"GND", "4":"GND"})
    two("R1", "CC1", "GND", "5.1k")
    two("R2", "CC2", "GND", "5.1k")
    pins("J2", {"1":"VBUS_USBA", "2":"USB_A_DM", "3":"USB_A_DP", "4":"GND", "5":"GND"})
    pins("J3", {"1":"VBUS_NATIVE", "2":"USB_NATIVE_DM", "3":"USB_NATIVE_DP", "4":None, "5":"GND", "6":"GND"})
    pins("U1", {"1":"MUX_EN_N", "2":"SEL1", "3":"USB_UART_DP", "4":"USB_SIL_DP", "5":"USB_A_DP",
                "6":"USB_NATIVE_DP", "7":"USB_UP_DP", "8":"GND", "9":"USB_UP_DM", "10":"USB_NATIVE_DM",
                "11":"USB_A_DM", "12":"USB_SIL_DM", "13":"USB_UART_DM", "14":"SEL0", "15":None, "16":"VBUS_IN"})
    for ref, prefix, supply in [("D1","USB_UP","VBUS_IN"), ("D2","USB_NATIVE","VBUS_NATIVE"), ("D3","USB_A","VBUS_USBA")]:
        pins(ref, {"1":prefix+"_DP", "6":prefix+"_DP", "3":prefix+"_DM", "4":prefix+"_DM", "2":"GND", "5":supply})

    # TPS2552DBV: active-low EN3, IN1, OUT6, GND2, FAULT4, ILIM5.
    for ref, enable, limit, output in [("U6","SERIAL_EN_N","ILIM_SERIAL","5V_SERIAL"),
                                      ("U9","NATIVE_EN_N","ILIM_NATIVE","VBUS_NATIVE"),
                                      ("U10","USBA_EN_N","ILIM_USBA","VBUS_USBA")]:
        check(f"{ref} active-low TPS2552DBVR", parts[ref]["mpn"] == "TPS2552DBVR")
        pins(ref, {"1":"VBUS_IN", "2":"GND", "3":enable, "4":"PWR_FAULT_N", "5":limit, "6":output})
    two("R6", "ILIM_SERIAL", "GND", "226k")
    two("R36", "ILIM_NATIVE", "GND", "52.3k")
    two("R37", "ILIM_USBA", "GND", "52.3k")
    pins("U5", {"1":"5V_SERIAL", "2":"GND", "3":"5V_SERIAL", "4":None, "5":"3V3"})
    for ref, net in [("R3","SEL1"), ("R4","SEL0"), ("R32","NATIVE_EN_N"), ("R33","USBA_EN_N"), ("R34","SERIAL_EN_N"), ("R35","MUX_EN_N")]:
        two(ref, net, "VBUS_IN", "47k")

    # Directed edge anode -> cathode: a grounded cathode pulls the anode low.
    diode_pins = {"D11":[("1","3"),("2","3")], "D12":[("2","1")],
                  "D13":[("2","1")], "D14":[("3","1"),("3","2")], "D15":[("2","1")]}
    diodes = [(parts[ref]["pins"][a], parts[ref]["pins"][k]) for ref, connections in diode_pins.items() for a,k in connections]
    switchpins = parts["SW1"]["pins"]
    # ALPS manufacturer's contact table, independently specified here.
    states = [("NATIVE", [(1,3),(6,8)], (0,0), "VBUS_NATIVE"),
              ("USB-A", [(2,3),(7,8)], (0,1), "VBUS_USBA"),
              ("SILVER", [(3,4),(8,9)], (1,0), "5V_SERIAL"),
              ("UART", [(3,5),(8,10)], (1,1), "5V_SERIAL"),
              ("OPEN_GAP", [], (1,1), None)]
    state_results = []
    enables = [("NATIVE_EN_N","VBUS_NATIVE"),("USBA_EN_N","VBUS_USBA"),("SERIAL_EN_N","5V_SERIAL")]
    for name, contacts, expected_bits, expected_power in states:
        edges = [(switchpins[str(a)], switchpins[str(b)]) for a,b in contacts]
        low = {"GND"}
        changed = True
        while changed:
            old = set(low)
            for a,b in edges:
                if a in low and b is not None: low.add(b)
                if b in low and a is not None: low.add(a)
            for anode,cathode in diodes:
                if cathode in low: low.add(anode)
            changed = old != low
        bits = (int("SEL1" not in low), int("SEL0" not in low))
        power = [out for en,out in enables if en in low]
        mux_enabled = "MUX_EN_N" in low
        check(f"SW1 {name}: select bits", bits == expected_bits, list(bits))
        check(f"SW1 {name}: exactly correct power branch", power == ([expected_power] if expected_power else []), power)
        check(f"SW1 {name}: mux enable", mux_enabled == bool(expected_power), mux_enabled)
        selected_index = bits[0]*2 + bits[1]
        dp_pin, dm_pin = [(6,10),(5,11),(4,12),(3,13)][selected_index]
        state_results.append({"mode":name, "contacts":contacts, "IN1_IN0":list(bits), "power":power,
                              "MUX_EN_N":0 if mux_enabled else 1,
                              "data_pair": [parts["U1"]["pins"][str(dp_pin)], parts["U1"]["pins"][str(dm_pin)]] if mux_enabled else []})

    # 8052 RHB pin numbers, exposed pad 33 is actual project library mapping.
    pins("U2", {"1":"SIL_VREGEN", "2":"SIL_SUSPEND", "3":"3V3", "4":"SIL_1V8", "5":"SIL_PUR",
                "6":"SIL_DP", "7":"SIL_DM", "8":"GND", "9":"SIL_RESET", "10":"SIL_SDA", "11":"SIL_SCL",
                "12":None, "13":"3V3", "14":"3V3", "15":"3V3", "16":"3V3", "17":"SIL_SIN",
                "18":"GND", "19":None, "20":None, "21":None, "22":None, "23":"SIL_TEST0", "24":"SIL_TEST1",
                "25":"3V3", "26":"SIL_X2", "27":"SIL_X1", "28":"GND", "29":"TI_GPIO_RING", "30":"TI_GPIO_TIP",
                "31":"TP_GPIO31", "32":"TP_GPIO30", "33":"GND"})
    two("R7", "USB_SIL_DP", "SIL_DP", "22R")
    two("R8", "USB_SIL_DM", "SIL_DM", "22R")
    two("R9", "SIL_PUR", "USB_SIL_DP", "1.5k")
    two("R10", "3V3", "SIL_RESET", "15k")
    two("R11", "SIL_RESET", "SIL_VREGEN", "32.4k")
    two("C11", "SIL_RESET", "GND")
    pins("D10", {"1":"SIL_SUSPEND", "2":"SIL_VREGEN"})
    two("R12", "3V3", "SIL_1V8", "90.9k")
    two("R13", "SIL_1V8", "GND", "100k")
    for ref, net in [("R14","SIL_TEST0"),("R15","SIL_TEST1"),("R16","SIL_SIN")]:
        two(ref, net, "3V3", "10k")
    pins("Y2", {"1":"SIL_X1", "2":"GND", "3":"SIL_X2", "4":"GND"})
    two("C12", "SIL_X1", "GND")
    two("C13", "SIL_X2", "GND")
    pins("J4", {"1":"TI_TIP", "2":"TI_RING", "3":"GND"})
    for suffix,q,d,rbase,rpull in [("TIP","Q1","D8","R19","R17"),("RING","Q2","D9","R20","R18")]:
        pins(q, {"1":"TI_BASE_"+suffix, "2":"TI_GPIO_"+suffix, "3":"TI_"+suffix})
        pins(d, {"1":"TI_"+suffix, "2":"TI_GPIO_"+suffix})
        two(rbase, "3V3", "TI_BASE_"+suffix, "10k")
        two(rpull, "3V3", "TI_GPIO_"+suffix, "10k")

    # EEPROM uses its own isolated rail and pull-ups for external programming.
    pins("U4", {"1":"GND", "2":"GND", "3":"GND", "4":"GND", "5":"EE_SDA", "6":"EE_SCL", "7":"EE_WP", "8":"EE_VCC"})
    pins("J8", {"1":"EE_VCC", "2":"GND", "3":"EE_SCL", "4":"EE_SDA", "5":"EE_WP", "6":"SIL_RESET"})
    pins("J9", {"1":"SIL_SCL", "2":"EE_SCL"})
    pins("J10", {"1":"EE_WP", "2":"GND"})
    two("R23", "SIL_SDA", "EE_SDA", "0R")
    two("R25", "3V3", "EE_VCC", "0R")
    two("R21", "EE_SDA", "EE_VCC", "4.7k")
    two("R22", "EE_SCL", "EE_VCC", "4.7k")
    two("R27", "EE_WP", "EE_VCC", "10k")
    check("No permanent parallel path around removable J9", all(not (set(p["pins"].values()) >= {"SIL_SCL","EE_SCL"}) for ref,p in parts.items() if ref != "J9"))

    # CH343P QFN-16 uses pad17 in the selected library, not datasheet alias0.
    pins("U3", {"1":"3V3", "2":"GND", "3":"5V_SERIAL", "4":"UART_TX", "5":"UART_RX", "6":"UART_V3",
                "7":"USB_UART_DP", "8":"USB_UART_DM", "9":"5V_SERIAL", "10":None,"11":None,"12":None,"13":None,"14":None,"15":None,"16":None,"17":"GND"})
    pins("U7", {"1":None,"2":"UART_TX","3":"GND","4":"UART_TX_OD","5":"3V3"})
    pins("U8", {"1":None,"2":"UART_RX_FILTER","3":"GND","4":"UART_RX","5":"3V3"})
    check("TX non-inverting open drain part", parts["U7"]["mpn"] == "SN74LVC1G07DBVR")
    check("RX non-inverting tolerant Schmitt part", parts["U8"]["mpn"] == "SN74LVC1G17DBVR")
    pins("D16", {"1":"UART_PULLUP", "2":"3V3"})
    two("R28", "UART_TX_OD", "UART_PULLUP", "10k")
    two("R29", "UART_TX_OD", "UART_TX_EXT", "1k")
    two("R30", "UART_RX_EXT", "UART_RX_FILTER", "1k")
    two("R31", "UART_RX_FILTER", "UART_PULLUP", "47k")
    pins("J5", {"1":"CASIO_RX","2":"CASIO_TX","3":"GND"})
    pins("J6", {"1":"GND","2":"AUX_RX","3":"AUX_TX","4":None})
    pins("J7", {"1":"CASIO_RX","2":"CASIO_TX","3":"UART_RX_EXT","4":"UART_TX_EXT","5":"AUX_RX","6":"AUX_TX"})
    check("UART modes paired and exclusive", design.get("uart_modes") == {"CASIO":[[1,3],[2,4]], "AUX":[[3,5],[4,6]], "OFF":[]})
    for ref, a,b in [("D4","TI_TIP","TI_RING"),("D5","CASIO_RX","CASIO_TX"),("D6","AUX_RX","AUX_TX"),("D7","CC1","CC2")]:
        pins(ref, {"1":a,"2":b,"3":"GND"})
    # Check every capacitor has a return and is not a shorted, orphan component.
    for ref,p in parts.items():
        if ref.startswith("C"):
            values = list(p["pins"].values())
            check(f"{ref} has ground return and distinct terminal", len(values)==2 and "GND" in values and len(set(values))==2)

    return {"pass":not errors, "component_count":len(parts), "named_net_count":len(groups),
            "check_count":len(checks), "errors":errors, "switch_states":state_results,
            "calculations":{"suspend_divider_unloaded_V":round(3.3*100/(90.9+100),6),
                            "UART_TX_pullup_current_upper_mA":round(3.3/(10+1),3)},
            "checks":checks,
            "scope":"Independent logical design audit only. No EDA export, PCB copper, analogue simulation or hardware measurement is implied."}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("design",type=Path)
    parser.add_argument("--output",type=Path)
    args=parser.parse_args()
    try:
        data=args.design.read_bytes()
        report=audit(json.loads(data))
        report["design_sha256"]=hashlib.sha256(data).hexdigest()
        pinmap={p["ref"]:p["pins"] for p in json.loads(data)["parts"]}
        report["logical_pin_map_sha256"]=hashlib.sha256(json.dumps(pinmap,sort_keys=True,separators=(",",":")).encode()).hexdigest()
        if args.output:
            args.output.parent.mkdir(parents=True,exist_ok=True)
            args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
        print(json.dumps({k:v for k,v in report.items() if k!="checks"},ensure_ascii=False,indent=2))
        return 0 if report["pass"] else 1
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"FAIL: {exc}")
        return 2


if __name__=="__main__":
    raise SystemExit(main())
