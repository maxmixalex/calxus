#!/usr/bin/env python3
"""Validate native BOM/CPL exports and prepare exactly the Calxus SMT subset.

Produces JSON tables for export_smt_csv.mjs. Centroids always come from native
CPL Mid X/Y; footprint origins must never be substituted for those columns.
"""
import argparse
import collections
import csv
import hashlib
import json
import math
from pathlib import Path
import re


def norm(value):
    return re.sub(r'[\s_#()（）-]+', '', value).lower()


ALIASES = {
    'ref': ('Designator', 'Designators', 'Reference', 'Ref', '位号'),
    'quantity': ('Quantity', 'Qty', '数量'),
    'footprint': ('Footprint', 'Package', '封装'),
    'supplier': ('Supplier Part', 'LCSC Part', 'LCSC Part #', 'LCSC', '立创编号', '供应商料号'),
    'mpn': ('Manufacturer Part', 'Manufacturer Part Number', 'MPN', '制造商料号'),
    'comment': ('Comment', 'Name', 'Value', '名称', '值'),
    'mid_x': ('Mid X', 'MidX', 'Mid X(mm)', 'Mid X(mil)', 'Center-X(mm)', '中心X'),
    'mid_y': ('Mid Y', 'MidY', 'Mid Y(mm)', 'Mid Y(mil)', 'Center-Y(mm)', '中心Y'),
    'ref_x': ('Ref X', 'RefX', 'Ref X(mm)', 'Ref X(mil)'),
    'ref_y': ('Ref Y', 'RefY', 'Ref Y(mm)', 'Ref Y(mil)'),
    'layer': ('Layer', 'Side', '层'),
    'rotation': ('Rotation', 'Angle', 'Rot', '旋转', '旋转角度'),
}


def read_csv(path, required, optional=()):
    raw = path.read_bytes()
    encoding = 'utf-16' if raw.startswith((b'\xff\xfe', b'\xfe\xff')) else 'utf-8-sig'
    text = raw.decode(encoding)
    # Native JLCEDA CSV exports can actually be UTF-16LE tab-separated data.
    # Select the delimiter from the real header, never the filename extension.
    delimiter = '\t' if '\t' in text.splitlines()[0] else ','
    rows = list(csv.DictReader(text.splitlines(), delimiter=delimiter))
    if not rows:
        raise ValueError(f'{path}: empty native CSV')
    mapping = {}
    for field, aliases in ALIASES.items():
        if field not in set(required) | set(optional):
            continue
        hits = [k for k in rows[0] if norm(k) in {norm(a) for a in aliases}]
        if len(hits) > 1:
            # Native CPL includes both Comment and Value. Equivalent duplicate
            # columns are unambiguous; conflicting values still fail closed.
            if any(len({(row[key] or '').strip() for key in hits}) > 1 for row in rows):
                raise ValueError(f'{path}: conflicting columns for {field}: {hits}')
        if hits:
            mapping[field] = hits[0]
    missing = set(required)-set(mapping)
    if missing:
        raise ValueError(f'{path}: required native columns absent: {sorted(missing)}; headers={list(rows[0])}')
    return [{k: (r[v] or '').strip() for k, v in mapping.items()} for r in rows], mapping


def refs(value):
    result = [s for s in re.split(r'[,;\s]+', value.strip()) if s]
    if not result or any(not re.fullmatch(r'[A-Z]+[0-9]+', r) for r in result):
        raise ValueError(f'Invalid/unexpanded designator list: {value!r}')
    if len(set(result)) != len(result):
        raise ValueError(f'Duplicate designator in one row: {value}')
    return result


def num(value):
    match = re.fullmatch(r'\s*([-+]?\d+(?:\.\d+)?)\s*(mm|mil|°)?\s*', value, re.I)
    if not match:
        raise ValueError(f'Invalid numeric cell {value!r}')
    return float(match.group(1)), (match.group(2) or '').lower()


def coordinate(value, unit):
    number, suffix = num(value)
    if suffix and suffix != unit:
        raise ValueError(f'Coordinate cell unit {suffix} conflicts with declared {unit}')
    return number*(0.0254 if unit == 'mil' else 1)


def part_sort(ref):
    return re.sub(r'\d+$', '', ref), int(re.search(r'\d+$', ref).group())


def prepare(args):
    design = json.loads(args.design.read_text())
    parts = {p['ref']: p for p in design['parts']}
    selected = {r: p for r, p in parts.items() if p['assembly'] == 'SMT'}
    if len(selected) != 87:
        raise ValueError(f'Expected reviewed 87-SMT contract, found {len(selected)}; review scope before changing checker')
    archive_audit = json.loads(args.native_metadata.read_text())
    if not archive_audit.get('pass'):
        raise ValueError('Native project archive metadata must come from a passing archive check')
    metadata = {p['ref']: p for p in archive_audit['metadata']}
    board = json.loads(args.pcb.read_text())
    actual = {p['ref']: p for p in board['components']}
    board_unit = board.get('units')
    if board_unit not in ('mil', 'mm'):
        raise ValueError('Actual PCB export must explicitly declare mil or mm units')
    scale = 0.0254 if board_unit == 'mil' else 1
    bom, bom_headers = read_csv(args.bom, ('ref', 'quantity', 'footprint', 'supplier'),
                                ('mpn', 'comment'))
    # Comment/Value are distinct native CPL fields and neither is used for
    # placement. Resolve only the identity, geometry and footprint columns.
    cpl, cpl_headers = read_csv(args.cpl, ('ref', 'mid_x', 'mid_y', 'rotation', 'layer'),
                                ('footprint', 'ref_x', 'ref_y'))
    for axis in ('mid_x', 'mid_y', 'ref_x', 'ref_y'):
        header = cpl_headers.get(axis, '')
        for unit in ('mm', 'mil'):
            if f'({unit})' in header.lower() and unit != args.cpl_unit:
                raise ValueError(f'CPL header {header} conflicts with --cpl-unit {args.cpl_unit}')
    seen_bom, seen_cpl, excluded = set(), set(), set()
    bom_out, cpl_out, checks = [], [], []
    for row in bom:
        row_refs = refs(row['ref'])
        if set(row_refs)-set(parts):
            raise ValueError(f'Unknown native BOM references: {set(row_refs)-set(parts)}')
        quantity, suffix = num(row['quantity'])
        if suffix or quantity != len(row_refs):
            raise ValueError(f'Native BOM quantity mismatch: {row_refs}: {row["quantity"]}')
        keep = [r for r in row_refs if r in selected]
        excluded.update(set(row_refs)-set(keep))
        if not keep:
            continue
        for ref in keep:
            if ref in seen_bom:
                raise ValueError(f'Duplicate native BOM reference {ref}')
            seen_bom.add(ref)
            p, m = selected[ref], metadata[ref]
            if row['supplier'] != p['lcsc'] or row['supplier'] != m['supplier_part']:
                raise ValueError(f'{ref}: supplier part differs between BOM, actual device and design')
            if row['footprint'] not in (m['footprint'], m['footprint_name']):
                raise ValueError(f'{ref}: native BOM footprint {row["footprint"]!r} differs from actual {m["footprint_name"]!r}')
            if row.get('mpn') and row['mpn'] != m['manufacturer_part']:
                raise ValueError(f'{ref}: native BOM manufacturer part differs from actual library')
            if not m['jlcpcb_part_class']:
                raise ValueError(f'{ref}: actual library has no JLCPCB class')
        comment = row.get('comment') or row.get('mpn') or metadata[keep[0]]['manufacturer_part']
        if not comment:
            raise ValueError(f'{keep}: native component comment/MPN is missing')
        bom_out.append([comment, ','.join(sorted(keep, key=part_sort)), row['footprint'], row['supplier'], len(keep)])
    for row in cpl:
        row_refs = refs(row['ref'])
        if len(row_refs) != 1:
            raise ValueError('CPL must contain one reference per row')
        ref = row_refs[0]
        if ref not in parts:
            raise ValueError(f'Unknown native CPL reference {ref}')
        if ref not in selected:
            excluded.add(ref)
            continue
        if ref in seen_cpl:
            raise ValueError(f'Duplicate CPL reference {ref}')
        seen_cpl.add(ref)
        p, m = actual[ref], metadata[ref]
        side = {'top': 'Top', 't': 'Top', 'toplayer': 'Top', '1': 'Top',
                'bottom': 'Bottom', 'b': 'Bottom', 'bottomlayer': 'Bottom', '2': 'Bottom'}.get(norm(row['layer']))
        expected_side = {1: 'Top', 2: 'Bottom'}.get(p['layer'])
        if side != expected_side or side is None:
            raise ValueError(f'{ref}: CPL side {row["layer"]!r} disagrees with actual layer {p["layer"]}')
        rotation, rotation_unit = num(row['rotation'])
        if rotation_unit not in ('', '°') or abs((rotation-p['rotation']+180)%360-180) > 1e-6:
            raise ValueError(f'{ref}: CPL rotation {rotation} disagrees with actual {p["rotation"]}')
        if row.get('footprint') and row['footprint'] not in (m['footprint'], m['footprint_name']):
            raise ValueError(f'{ref}: CPL footprint disagrees with actual library')
        origin_checked = False
        if 'ref_x' in row and 'ref_y' in row:
            for axis in ('x', 'y'):
                if abs(coordinate(row['ref_'+axis], args.cpl_unit)-p[axis]*scale) > 0.03:
                    raise ValueError(f'{ref}: CPL reference origin differs from actual PCB {axis}')
            origin_checked = True
        mx, my = coordinate(row['mid_x'], args.cpl_unit), coordinate(row['mid_y'], args.cpl_unit)
        if not (math.isfinite(mx) and math.isfinite(my)):
            raise ValueError(f'{ref}: invalid centroid')
        cpl_out.append([ref, round(mx, 6), round(my, 6), side, rotation % 360])
        checks.append({'ref': ref, 'class': m['jlcpcb_part_class'], 'side': side,
                       'rotation': rotation % 360, 'mid_mm': [mx, my],
                       'native_reference_origin_checked': origin_checked})
    if seen_bom != set(selected) or seen_cpl != set(selected):
        raise ValueError(f'Exact SMT scope failed: missing BOM={sorted(set(selected)-seen_bom)}, CPL={sorted(set(selected)-seen_cpl)}')
    cpl_out.sort(key=lambda r: part_sort(r[0]))
    report = {'pass': True, 'scope': 'Native BOM/CPL subset and identity/rotation/side comparison; no assembly-machine orientation approval or hardware testing',
              'smt_count': len(selected), 'bom_rows': len(bom_out), 'cpl_rows': len(cpl_out),
              'class_counts': dict(collections.Counter(c['class'] for c in checks)),
              'excluded_refs': sorted(excluded, key=part_sort), 'component_checks': checks,
              'source_sha256': {k: hashlib.sha256(getattr(args, k).read_bytes()).hexdigest()
                                for k in ('bom', 'cpl', 'pcb', 'design', 'native_metadata')},
              'native_archive_sha256': archive_audit['archive_sha256'],
              'centroid_rule': 'Native Mid X/Y retained; converted only from declared unit to mm. Ref X/Y never substituted.'}
    tables = {'validation': report,
              'bom': [['Comment', 'Designator', 'Footprint', 'LCSC Part #', 'Quantity']]+bom_out,
              'cpl': [['Designator', 'Mid X', 'Mid Y', 'Layer', 'Rotation']]+cpl_out}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(tables, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({k: report[k] for k in ('pass', 'smt_count', 'bom_rows', 'cpl_rows', 'class_counts')}, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('bom', 'cpl', 'pcb', 'design', 'native-metadata', 'output'):
        parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--cpl-unit', choices=('mm', 'mil'), required=True)
    args = parser.parse_args()
    try:
        prepare(args)
    except (ValueError, KeyError, OSError) as exc:
        parser.exit(2, f'FAIL: {exc}\n')
