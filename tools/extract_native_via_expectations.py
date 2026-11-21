#!/usr/bin/env python3
"""Extract every real VIA hole from the final native epro2 source archive.

Source values use mil; API getter values are not used as drill dimensions.
The optional routing manifest identifies the 128 required tented vias, while
their centres and sizes are independently taken from the saved native source.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import zipfile

from check_native_project_archive import parse_source, records


def extract(archive, pcb_id, manifest_path=None):
    with zipfile.ZipFile(archive) as z:
        if z.testzip() is not None:
            raise ValueError('Native project CRC failure')
        names = [n for n in z.namelist() if n.endswith('.epru')]
        if len(names) != 1:
            raise ValueError('Expected one native project source')
        source = z.read(names[0])
    pcbs = [d for d in parse_source(source.decode()) if d['head'].get('uuid') == pcb_id
            and d['head'].get('docType') == 'PCB']
    if len(pcbs) != 1:
        raise ValueError('Expected exactly one specified PCB in native archive')
    vias = []
    for h, d in records(pcbs[0], 'VIA'):
        if d.get('viaType') != 'NORMAL':
            raise ValueError(f'{h["id"]}: non-normal via needs explicit machining review')
        x, y, hole, outer = [float(d[k])*.0254 for k in ('centerX', 'centerY', 'holeDiameter', 'viaDiameter')]
        if not all(math.isfinite(v) for v in (x, y, hole, outer)) or not 0 < hole < outer < 2:
            raise ValueError(f'{h["id"]}: invalid source via geometry')
        vias.append({'primitiveId': h['id'], 'net': d['netName'], 'center_mm': [x, y],
                     'hole_diameter_mm': hole, 'outer_diameter_mm': outer,
                     'plated': True, 'shape': 'ROUND', 'source_via_type': d['viaType'],
                     'source_mask_expansion_mil': {'top': d.get('topSolderExpansion'),
                                                    'bottom': d.get('bottomSolderExpansion')}})
    if not vias or len({v['primitiveId'] for v in vias}) != len(vias):
        raise ValueError('Empty or duplicate native via population')
    report = {'schema': 'calxus.native-all-via-drill-expectations.v1', 'units': 'mm',
              'pcbId': pcb_id, 'source_archive_sha256': hashlib.sha256(archive.read_bytes()).hexdigest(),
              'source_epru_sha256': hashlib.sha256(source).hexdigest(),
              'expected_count': len(vias), 'vias': vias,
              'scope': 'Every VIA record in the saved native PCB; nominal drilling geometry only, not fabrication-file acceptance'}
    tenting = None
    if manifest_path:
        manifest = json.loads(manifest_path.read_text())
        actual_by_id = {v['primitiveId']: v for v in vias}
        selected = manifest.get('records', manifest.get('vias', []))
        if len(selected) != 128 or len({v['primitiveId'] for v in selected}) != 128:
            raise ValueError('Routing manifest must identify exactly 128 unique added/restored vias')
        tents = []
        for m in selected:
            v = actual_by_id[m['primitiveId']]
            mcenter = m.get('center_mm', [m.get('x_mm'), m.get('y_mm')])
            mhole = m.get('hole_diameter_mm', m.get('holeDiameter_mm'))
            if math.dist(v['center_mm'], mcenter) > .003 or abs(v['hole_diameter_mm']-mhole) > .003:
                raise ValueError(f'{v["primitiveId"]}: saved source differs from the native routing manifest')
            tents.append({**v, 'route_tag': m.get('tag'), 'route_plan_sha256': manifest.get('planSHA256')})
        vippo = manifest.get('originalVIPPO', [])
        if len(vippo) != 4 or {v['primitiveId'] for v in vippo} & {v['primitiveId'] for v in tents}:
            raise ValueError('Four separately classified EP VIPPO vias are required')
        report['separate_ep_vippo'] = [{**actual_by_id[m['primitiveId']], 'footprint_pad': m['footprintPad']} for m in vippo]
        tenting = {**{k: report[k] for k in ('units', 'pcbId', 'source_archive_sha256', 'source_epru_sha256')},
                   'schema': 'calxus.native-tented-via-expectations.v1', 'expected_count': 128,
                   'manifest_sha256': hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
                   'route_plan_sha256': manifest.get('planSHA256'), 'vias': tents,
                   'scope': 'The 128 native routing-manifest vias, using independently saved native source dimensions; excludes four EP VIPPO vias'}
    return report, tenting


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('archive', type=Path)
    p.add_argument('--pcb-id', default='2a0c39c6c6694f40')
    p.add_argument('--route-manifest', type=Path)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--tenting-output', type=Path)
    args = p.parse_args()
    result, tents = extract(args.archive, args.pcb_id, args.route_manifest)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    if args.tenting_output:
        if tents is None:
            raise ValueError('--route-manifest is required for --tenting-output')
        args.tenting_output.parent.mkdir(parents=True, exist_ok=True)
        args.tenting_output.write_text(json.dumps(tents, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'source_archive_sha256': result['source_archive_sha256'],
                      'all_vias': result['expected_count'], 'tented_vias': len(tents['vias']) if tents else None}))
