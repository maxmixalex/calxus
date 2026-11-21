#!/usr/bin/env python3
"""Check a native Calxus epro2 export against its electrical/layout contract.

Reads embedded SYMBOL/PIN geometry, actual COMPONENT poses, LINE connectivity,
WIRE NET attributes and explicit NC flags. It does not trust a previous API
netlist or assume that Document.save() returned success. This is a deliberately
scoped checker for the unrotated three-page Calxus schematic, including the
explicitly planned horizontal mirror on the r7 J2 replacement symbol.
"""
import argparse
import collections
import hashlib
import json
from pathlib import Path
import zipfile


def parse_source(text):
    docs = []
    current = None
    for line in text.splitlines():
        if not line.strip():
            continue
        header, data = line.split('||', 1)
        header = json.loads(header)
        data = data.removesuffix('|')
        data = json.loads(data) if data not in ('', '|') else None
        if header['type'] == 'DOCHEAD':
            current = {'head': data, 'records': {}}
            docs.append(current)
        else:
            # Empty data is a native deleted-record tombstone. Last record wins.
            current['records'][(header['type'], header['id'])] = (header, data)
    for doc in docs:
        doc['records'] = [r for r in doc['records'].values() if r[1] is not None]
    return docs


def records(doc, kind):
    return [(h, d) for h, d in doc['records'] if h['type'] == kind]


def attributes(doc):
    result = collections.defaultdict(dict)
    for _, data in records(doc, 'ATTR'):
        result[data['parentId']][data['key']] = data['value']
    return result


def on_line(x, y, line):
    x1, y1, x2, y2 = (line[k] for k in ('startX', 'startY', 'endX', 'endY'))
    return (abs((x-x1)*(y2-y1)-(y-y1)*(x2-x1)) < 1e-7
            and min(x1, x2)-1e-7 <= x <= max(x1, x2)+1e-7
            and min(y1, y2)-1e-7 <= y <= max(y1, y2)+1e-7)


def audit(archive, design_path, plan_path):
    design = json.loads(design_path.read_text())
    expected = {p['ref']: p for p in design['parts'] if not p.get('pcb_only')}
    plan = json.loads(plan_path.read_text())
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None, 'Archive CRC error'
        sources = [n for n in z.namelist() if n.endswith('.epru')]
        assert len(sources) == 1, f'Expected one epru source, found {sources}'
        source = z.read(sources[0])
        docs = parse_source(source.decode('utf-8'))
        entries = [{'name': i.filename, 'bytes': i.file_size} for i in z.infolist()]
    by_uuid = {d['head']['uuid']: d for d in docs}
    issues, poses, pin_results, metadata = [], [], [], []
    seen = set()
    pages = []
    compact = {'components': {}}
    for doc in docs:
        if doc['head']['docType'] != 'SCH_PAGE':
            continue
        page_name = records(doc, 'META')[0][1]['title']
        attrs = attributes(doc)
        wires = {h['id']: d for h, d in records(doc, 'WIRE')}
        lines = [d for _, d in records(doc, 'LINE') if d.get('lineGroup') in wires]
        groups = {wid: attrs.get(wid, {}).get('NET') for wid in wires}
        pages.append({'name': page_name, 'uuid': doc['head']['uuid'],
                      'wire_groups': len(wires), 'wire_segments': len(lines)})
        for wid, net in groups.items():
            if not net:
                issues.append(f'{page_name}: WIRE {wid} lacks a NET attribute')
        for header, component in records(doc, 'COMPONENT'):
            cid = header['id']
            ca = attrs[cid]
            ref = ca.get('Designator')
            if ref not in expected:
                if ref and not ref.endswith('?'):
                    issues.append(f'Unexpected schematic component {ref}')
                continue
            if ref in seen:
                issues.append(f'Duplicate component {ref}')
            seen.add(ref)
            if component.get('rotation', 0) != 0:
                raise ValueError(f'{ref}: rotated symbols are outside this checker scope')
            want = plan['components'][ref]
            actual_pose = {'x': component['x'], 'y': -component['y'],
                           'rotation': component.get('rotation', 0), 'sheet': page_name}
            pose_ok = all(actual_pose[k] == want[k] for k in actual_pose)
            actual_pose['mirror'] = component.get('isMirror', False)
            pose_ok = pose_ok and actual_pose['mirror'] == want.get('mirror', False)
            poses.append({'ref': ref, 'actual': actual_pose, 'pass': pose_ok})
            if not pose_ok:
                issues.append(f'{ref}: source pose differs from functional plan')
            sym = by_uuid[ca['Symbol']]
            sym_attrs = attributes(sym)
            device_uuid = ca.get('Device') or json.loads(component['attrs']['DeviceName'])['uuid']
            device = by_uuid[device_uuid]
            da = records(device, 'META')[0][1]['attributes']
            # Null/empty instance values inherit the native DEVICE attributes.
            properties = dict(da)
            properties.update({k: v for k, v in ca.items() if v not in (None, '')})
            supplier = properties.get('Supplier Part')
            footprint = properties.get('Footprint')
            fp = by_uuid.get(footprint)
            mp = {'ref': ref, 'supplier_part': supplier, 'device': device_uuid,
                  'footprint': footprint, 'footprint_name': json.loads(da.get('FootprintName') or '{}').get('name'),
                  'manufacturer_part': properties.get('Manufacturer Part'),
                  'jlcpcb_part_class': properties.get('JLCPCB Part Class'),
                  'pass': supplier == expected[ref]['lcsc'] and fp is not None and fp['head']['docType'] == 'FOOTPRINT'}
            metadata.append(mp)
            if not mp['pass']:
                issues.append(f'{ref}: missing or mismatched native device/footprint/supplier association')
            net_pins = {}
            actual_pin_numbers = set()
            for ph, pin in records(sym, 'PIN'):
                if pin.get('partId') != component['partId']:
                    continue
                number = str(sym_attrs[ph['id']]['Pin Number'])
                actual_pin_numbers.add(number)
                x = component['x'] + (-pin['x'] if component.get('isMirror', False) else pin['x'])
                y = component['y'] + pin['y']
                touching = {groups[l['lineGroup']] for l in lines if on_line(x, y, l)}
                touching.discard(None)
                nc = attrs.get(cid+'-'+ph['id'], {}).get('NO_CONNECT') == 'yes'
                expected_net = expected[ref]['pins'].get(number)
                actual_net = next(iter(touching)) if len(touching) == 1 else None
                ok = ((expected_net is None and not touching and nc)
                      or (expected_net is not None and touching == {expected_net} and not nc))
                pin_results.append({'ref': ref, 'pin': number, 'x': x, 'y': -y,
                                    'expected_net': expected_net, 'actual_nets': sorted(touching),
                                    'no_connect': nc, 'pass': ok})
                if not ok:
                    issues.append(f'{ref}.{number}: expected {expected_net!r}, actual {sorted(touching)}, NC={nc}')
                net_pins[number] = {'number': number, 'net': actual_net or ''}
            if actual_pin_numbers != set(expected[ref]['pins']):
                issues.append(f'{ref}: symbol pin numbers differ from design contract')
            compact['components'][cid] = {'props': {'Designator': ref, 'Supplier Part': supplier,
                                                    'Device': device_uuid, 'Footprint': footprint},
                                          'pinInfoMap': net_pins}
    if seen != set(expected):
        issues.append(f'Missing references: {sorted(set(expected)-seen)}')
    report = {'scope': 'Independent offline native epro2 archive check; not a reopened-editor ERC/DRC test',
              'archive': str(archive), 'archive_bytes': archive.stat().st_size,
              'archive_sha256': hashlib.sha256(archive.read_bytes()).hexdigest(),
              'source_sha256': hashlib.sha256(source).hexdigest(), 'entries': entries,
              'doc_types': dict(collections.Counter(d['head']['docType'] for d in docs)),
              'pages': pages, 'components': len(seen), 'pins': len(pin_results),
              'explicit_nc': sum(p['no_connect'] for p in pin_results),
              'positions': poses, 'metadata': metadata, 'pin_checks': pin_results,
              'issues': issues, 'pass': not issues}
    return report, compact


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    parser.add_argument('--design', type=Path, required=True)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--netlist', type=Path)
    args = parser.parse_args()
    report, compact = audit(args.archive, args.design, args.plan)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    if args.netlist:
        args.netlist.write_text(json.dumps(compact, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({k: report[k] for k in ('pass', 'components', 'pins', 'explicit_nc', 'issues', 'archive_sha256')}, ensure_ascii=False))
    raise SystemExit(0 if report['pass'] else 1)
