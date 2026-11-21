#!/usr/bin/env python3
"""Prove the offline candidate preserves the native 87-SMT export geometry.

Also extracts a complete 97-component plus 23-testpad PCB pin/net list directly
from the saved archive. This is source inspection, not a live EDA export or DRC.
"""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile
from check_native_project_archive import parse_source, records, attributes


def read_archive(path):
    with zipfile.ZipFile(path) as z:
        if z.testzip() is not None:
            raise ValueError('Archive CRC failure')
        names = [n for n in z.namelist() if n.endswith('.epru')]
        if len(names) != 1:
            raise ValueError('Expected one native source')
        docs = parse_source(z.read(names[0]).decode())
    by_id = {d['head']['uuid']: d for d in docs}
    pcbs = [d for d in docs if d['head']['docType'] == 'PCB']
    if len(pcbs) != 1:
        raise ValueError('Expected one PCB')
    pcb = pcbs[0]; attrs = attributes(pcb)
    components = {attrs[h['id']]['Designator']: (h, d, attrs[h['id']]) for h, d in records(pcb, 'COMPONENT')}
    return by_id, pcb, components


def semantic_records(doc):
    return {(h['type'], h['id']): d for h, d in doc['records']}


def audit(args):
    design = json.loads(args.design.read_text())
    smt = {p['ref'] for p in design['parts'] if p['assembly'] == 'SMT'}
    if len(smt) != 87:
        raise ValueError('Expected 87 reviewed SMT references')
    now, pcb, components = read_archive(args.candidate)
    old, _, baseline = read_archive(args.native_export_archive)
    native_pads = json.loads(args.native_pads.read_text())
    if native_pads['units'] != 'mil':
        raise ValueError('Expected the actual saved native mil pad audit')
    native = {p['ref']: p for p in native_pads['components']}
    source_pose = {'schema': 'calxus.offline-candidate-component-poses.v1', 'units': 'mil',
                   'source_archive_sha256': hashlib.sha256(args.candidate.read_bytes()).hexdigest(),
                   'scope': 'Read directly from saved candidate source; not a fresh native PCB API export', 'components': []}
    checks, errors = [], []
    for ref in sorted(smt):
        _, c, a = components[ref]; _, b, ba = baseline[ref]; n = native[ref]
        pose = {k: c[k] for k in ('x', 'y', 'angle', 'layerId')}
        preserved = pose == {k: b[k] for k in pose}
        agrees = (abs(c['x']-n['x']) < .0002 and abs(c['y']-n['y']) < .0002
                  and abs((c['angle']-n['rotation']+180)%360-180) < 1e-6 and c['layerId'] == n['layer'])
        footprint = a['Footprint'] == ba['Footprint'] == n['footprint']['uuid']
        fp_records = footprint and semantic_records(now[a['Footprint']]) == semantic_records(old[ba['Footprint']])
        device = a['Device'] == ba['Device'] and semantic_records(now[a['Device']]) == semantic_records(old[ba['Device']])
        item = {'ref': ref, 'pose_mil': pose, 'pose_matches_native_source_archive': preserved,
                'pose_matches_saved_native_api': agrees, 'footprint_identity_preserved': footprint,
                'saved_native_api_rotation_degrees': n['rotation'],
                'all_footprint_records_preserved': fp_records, 'device_records_preserved': device,
                'pass': all((preserved, agrees, footprint, fp_records, device))}
        checks.append(item)
        if not item['pass']:
            errors.append(ref+': native SMT source/pose preservation failed')
    compact = {'components': {}}
    pad_nets = {}
    for h, d in records(pcb, 'PAD_NET'):
        key = json.loads(h['id']); pad_nets[(key[1], key[3])] = d['padNet']
    for ref, (h, c, a) in components.items():
        cid = h['id']; pins = {}
        for ph, p in records(now[a['Footprint']], 'PAD'):
            number = str(p['num'])
            if number in pins:
                raise ValueError(f'{ref}: duplicate physical source pad number requires explicit handling')
            pins[number] = {'number': number, 'net': pad_nets.get((cid, ph['id']), '') or ''}
        compact['components'][cid] = {'props': {'Designator': ref}, 'pinInfoMap': pins}
        source_pose['components'].append({'ref': ref, 'id': cid, 'x': c['x'], 'y': c['y'],
                                          'rotation': c['angle'], 'layer': c['layerId'],
                                          'footprint': {'uuid': a['Footprint']}})
    for h, p in records(pcb, 'PAD'):
        ref = str(p.get('num', ''))
        if ref.startswith('TP'):
            compact['components'][h['id']] = {'props': {'Designator': ref},
                'pinInfoMap': {'1': {'number': '1', 'net': p.get('netName', '') or ''}}}
    report = {'pass': not errors, 'schema': 'calxus.offline-candidate-smt-preservation.v1',
              'scope': 'Source-based equivalence preserves existing native BOM/CPL applicability for the unchanged 87-SMT subset; no fresh native export, soldering or assembly-machine orientation approval',
              'candidate_sha256': hashlib.sha256(args.candidate.read_bytes()).hexdigest(),
              'native_export_archive_sha256': hashlib.sha256(args.native_export_archive.read_bytes()).hexdigest(),
              'native_pads_sha256': hashlib.sha256(args.native_pads.read_bytes()).hexdigest(),
              'design_sha256': hashlib.sha256(args.design.read_bytes()).hexdigest(),
              'checked_smt_count': len(checks), 'preserved_smt_count': sum(c['pass'] for c in checks),
              'checks': checks, 'errors': errors}
    return report, compact, source_pose


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for key in ('candidate', 'native-export-archive', 'native-pads', 'design', 'report', 'netlist', 'poses'):
        p.add_argument('--'+key, type=Path, required=True)
    args = p.parse_args(); report, netlist, poses = audit(args)
    for path, data in ((args.report, report), (args.netlist, netlist), (args.poses, poses)):
        path.parent.mkdir(parents=True, exist_ok=True); path.write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({k: report[k] for k in ('pass', 'candidate_sha256', 'checked_smt_count', 'preserved_smt_count', 'errors')}))
    raise SystemExit(0 if report['pass'] else 1)
