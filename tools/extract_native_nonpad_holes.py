#!/usr/bin/env python3
"""Extract the two separately verified J1 non-PAD locating holes.

Native layer12 is Multi-Layer, not the board-outline layer. These specific
FILL circles have independently been confirmed as holes in the native Board
BREP. Their CAM representation still has to be checked in actual fabrication
files. Other unknown Multi-Layer fills are refused, not inferred to be holes.
"""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile
from check_native_project_archive import parse_source, records, attributes
from extract_native_tht_drills import xy_transform


def extract(archive):
    with zipfile.ZipFile(archive) as z:
        if z.testzip() is not None:
            raise ValueError('Native archive CRC failure')
        names = [n for n in z.namelist() if n.endswith('.epru')]
        if len(names) != 1:
            raise ValueError('Expected one native source')
        raw = z.read(names[0])
    docs = parse_source(raw.decode()); by_id = {d['head']['uuid']: d for d in docs}
    pcbs = [d for d in docs if d['head']['docType'] == 'PCB']
    if len(pcbs) != 1:
        raise ValueError('Expected one PCB')
    pcb = pcbs[0]; attrs = attributes(pcb); holes = []
    for ch, c in records(pcb, 'COMPONENT'):
        ref = attrs[ch['id']].get('Designator'); fp_id = attrs[ch['id']]['Footprint']
        for h, d in records(by_id[fp_id], 'FILL'):
            if d.get('layerId') != 12:
                continue
            path = d.get('path', [])
            if ref != 'J1' or h['id'] not in ('e55', 'e56') or len(path) != 1 or path[0][0] != 'CIRCLE' or len(path[0]) != 4 or c['layerId'] != 1:
                raise ValueError(f'Unreviewed Multi-Layer FILL {ref}:{h["id"]}; do not infer its machining role')
            _, x, y, radius = path[0]
            holes.append({'ref': ref, 'source_id': h['id'], 'component_id': ch['id'],
                          'footprint_uuid': fp_id, 'shape': 'ROUND', 'plated': False,
                          'center_mm': xy_transform(x, y, c['x'], c['y'], c.get('angle', 0)),
                          'diameter_mm': 2*radius*.0254, 'source_record': d})
    if any(d.get('layerId') == 12 for _, d in records(pcb, 'FILL')):
        raise ValueError('Unreviewed free-board Multi-Layer FILL')
    if len(holes) != 2 or {h['source_id'] for h in holes} != {'e55', 'e56'}:
        raise ValueError('The two verified J1 locating features are missing or duplicated')
    return {'schema': 'calxus.native-nonpad-hole-expectations.v1', 'units': 'mm',
            'source_archive_sha256': hashlib.sha256(archive.read_bytes()).hexdigest(),
            'source_epru_sha256': hashlib.sha256(raw).hexdigest(), 'expected_count': 2,
            'source_layer_semantics': 'Multi-Layer12 FILL, not PAD and not Board Outline11',
            'physical_hole_confirmation': 'mechanical/validation/native-r7-j1-multilayer-hole-evidence.json',
            'holes': holes, 'scope': 'Two J1 locating holes additional to the 56 PAD-defined holes and all VIA records; require exactly one machining representation per hole'}


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('archive', type=Path)
    p.add_argument('--output', type=Path, required=True); a = p.parse_args()
    result = extract(a.archive); a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'nonpad_holes': len(result['holes']), 'source_archive_sha256': result['source_archive_sha256']}))
