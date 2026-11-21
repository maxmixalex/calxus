#!/usr/bin/env python3
"""Patch only Calxus physical layers in a NEW native epro2 archive.

Use a fresh export after routing. This script never contacts the editor, never
overwrites its input, and preserves every non-layer source line byte-for-byte.
After official import into a new EPRJ3 project, independently verify getStackup
and the Board STEP BREP. Offline validation is not an imported-editor result.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import zipfile

PCB_UUID = '2a0c39c6c6694f40'
MM_PER_ARCHIVE_UNIT = .0254
# id: thickness mm, material, permittivity, loss tangent, physical zIndex
TARGET = {
    3: (0, None, None, None, 1),
    7: (0, None, None, None, 2),
    5: (.01, 'Solder mask', 3.8, .02, 3),
    1: (.035, 'Copper 1oz', None, None, 1000),
    361: (.2104, '7628 prepreg', 4.4, .02, 1001),
    15: (.0152, 'Copper 0.5oz', None, None, 2000),
    362: (1.065, 'FR-4 core', 4.38, .02, 2001),
    16: (.0152, 'Copper 0.5oz', None, None, 3000),
    363: (.2104, '7628 prepreg', 4.4, .02, 3001),
    2: (.035, 'Copper 1oz', None, None, 9000),
    6: (.01, 'Solder mask', 3.8, .02, 10000),
    8: (0, None, None, None, 10001),
    4: (0, None, None, None, 10002),
}
SUBSTRATES = {361: 'PP7628 top', 362: 'FR4 core', 363: 'PP7628 bottom'}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def parse_lines(source, uuid):
    rows = []
    active = False
    matching_heads = 0
    for index, line in enumerate(source.decode('utf-8').splitlines(keepends=True)):
        if not line.strip():
            rows.append({'index': index, 'raw': line, 'active': active, 'h': {}, 'd': None})
            continue
        head, data = line.rstrip('\r\n').split('||', 1)
        h = json.loads(head)
        data = data.removesuffix('|')
        d = json.loads(data) if data else None
        if h['type'] == 'DOCHEAD':
            active = d.get('uuid') == uuid
            if active:
                matching_heads += 1
                assert d.get('docType') == 'PCB', 'Target UUID is not a PCB'
        rows.append({'index': index, 'raw': line, 'active': active, 'h': h, 'd': d})
    assert matching_heads == 1, f'Expected one target PCB, found {matching_heads}'
    return rows


def layer_id(row):
    return json.loads(row['h']['id'])[1]


def mutable(row):
    return row['active'] and (row['h'].get('type') == 'LAYER_PHYS' or
        (row['h'].get('type') == 'LAYER' and layer_id(row) in SUBSTRATES))


def protected_bytes(rows):
    return ''.join(r['raw'] for r in rows if not mutable(r)).encode('utf-8')


def patch(source, uuid):
    rows = parse_lines(source, uuid)
    board = [r for r in rows if r['active']]
    indexed = {}
    for r in board:
        if r['h'].get('type') not in {'LAYER', 'LAYER_PHYS'}:
            continue
        key = (r['h']['type'], layer_id(r))
        assert key not in indexed, f'Duplicate native layer key {key}; resolve before patching'
        assert r['d'] is not None, f'Layer tombstone requires explicit review: {key}'
        indexed[key] = r
    physical_ids = {key[1] for key in indexed if key[0] == 'LAYER_PHYS'}
    assert physical_ids <= set(TARGET), f'Unexpected physical layers: {physical_ids-set(TARGET)}'
    used_copper = {n for (kind, n), r in indexed.items() if kind == 'LAYER' and
        r['d']['layerType'] in {'TOP','BOTTOM','SIGNAL','PLANE'} and r['d'].get('use')}
    assert used_copper == {1,15,16,2}, f'Expected existing four-layer PCB, got {used_copper}'
    # Calibrated from this client's real epro2 plus measured STEP, not display units.
    # The current doc.format comment claims 0.1 mm units, which contradicts these
    # exported values and the exact old-parameter STEP reconstruction.
    for lid in [1,2]:
        value = indexed[('LAYER_PHYS',lid)]['d']['thickness']
        assert .015 < value*MM_PER_ARCHIVE_UNIT < .07, 'Archive unit calibration failed'
    template = indexed[('LAYER',361)]['d']
    assert template['layerType'] == 'SUBSTRATE'
    next_ticket = max((r['h'].get('ticket',0) for r in board),default=0)+1
    replacements, insertions, changes = {}, {}, []
    anchors = {kind:max(r['index'] for r in board if r['h'].get('type') == kind)
               for kind in ['LAYER','LAYER_PHYS']}

    def replace(kind, lid, data):
        nonlocal next_ticket
        old = indexed.get((kind,lid))
        if old is not None and old['d'] == data:
            return
        if old is None:
            h = {'type':kind,'ticket':next_ticket,'id':json.dumps([kind,lid],separators=(',',':')),
                 'firstTicket':next_ticket}
        else:
            h = copy.deepcopy(old['h'])
            h['ticket'] = next_ticket
        next_ticket += 1
        ending = '\r\n' if old and old['raw'].endswith('\r\n') else '\n'
        line = json.dumps(h,ensure_ascii=False,separators=(',',':'))+'||'+json.dumps(data,ensure_ascii=False,separators=(',',':'))+'|'+ending
        if old:
            replacements[old['index']] = line
        else:
            insertions.setdefault(anchors[kind],[]).append(line)
        changes.append({'type':kind,'layer_id':lid,'before':old['d'] if old else None,'after':data})

    for lid, name in SUBSTRATES.items():
        old = indexed.get(('LAYER',lid))
        data = copy.deepcopy(old['d'] if old else template)
        data.update(layerId=lid,layerType='SUBSTRATE',layerName=name,use=True)
        replace('LAYER',lid,data)
    for lid, (mm, material, er, loss, zindex) in TARGET.items():
        old = indexed.get(('LAYER_PHYS',lid))
        data = copy.deepcopy(old['d'] if old else {'isKeepIsland':True})
        data.update(thickness=mm/MM_PER_ARCHIVE_UNIT,material=material,
                    permittivity=er,lossTangent=loss,zIndex=zindex)
        replace('LAYER_PHYS',lid,data)
    result = ''.join(replacements.get(r['index'],r['raw'])+''.join(insertions.get(r['index'],[]))
                     for r in rows).encode('utf-8')
    after_rows = parse_lines(result,uuid)
    assert protected_bytes(rows) == protected_bytes(after_rows), 'Non-layer bytes changed'
    after_physical = [r for r in after_rows if r['active'] and r['h'].get('type')=='LAYER_PHYS']
    assert len(after_physical) == 13
    ordered = sorted(after_physical,key=lambda r:r['d']['zIndex'])
    assert [layer_id(r) for r in ordered] == list(TARGET)
    total = sum(r['d']['thickness']*MM_PER_ARCHIVE_UNIT for r in ordered)
    assert abs(total-1.6062) < 1e-10
    return result, {'pcb_uuid':uuid,'physical_layer_count':len(ordered),
        'physical_order':[layer_id(r) for r in ordered],
        'total_including_masks_mm':total,'target_finished_nominal_mm':1.6,
        'archive_mm_per_unit':MM_PER_ARCHIVE_UNIT,
        'unit_basis':'Measured current epro2/STEP mapping. doc.format TLayerPhys 0.1-mm comment is contradicted by the native archive and measured BREP.',
        'source_sha256_before':sha(source),'source_sha256_after':sha(result),
        'all_non_layer_source_bytes_unchanged':True,
        'non_layer_bytes_sha256':sha(protected_bytes(rows)),
        'changed_or_added_records':changes,
        'D3_ATTRIBUTE_preserved':True,
        'editor_import_verified':False,'actual_step_verified':False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input',type=Path)
    parser.add_argument('output',type=Path)
    parser.add_argument('--pcb-uuid',default=PCB_UUID)
    parser.add_argument('--report',type=Path,required=True)
    args = parser.parse_args()
    assert args.input.resolve() != args.output.resolve(), 'Never overwrite the source archive'
    assert not args.output.exists(), 'Choose a new output filename'
    before_hash = sha(args.input.read_bytes())
    with zipfile.ZipFile(args.input) as archive:
        assert archive.testzip() is None
        sources = [n for n in archive.namelist() if n.endswith('.epru')]
        assert len(sources)==1, f'Expected one epru, found {sources}'
        source_name = sources[0]
        source = archive.read(source_name)
        updated, report = patch(source,args.pcb_uuid)
        args.output.parent.mkdir(parents=True,exist_ok=True)
        with zipfile.ZipFile(args.output,'w') as out:
            for info in archive.infolist():
                out.writestr(copy.copy(info),updated if info.filename==source_name else archive.read(info.filename))
            out.comment = archive.comment
        with zipfile.ZipFile(args.output) as out:
            assert out.testzip() is None
            assert out.namelist() == archive.namelist()
            for name in archive.namelist():
                if name != source_name:
                    assert out.read(name) == archive.read(name), f'Other ZIP entry changed: {name}'
    assert sha(args.input.read_bytes()) == before_hash
    report.update(input_archive=str(args.input),input_sha256=before_hash,
                  output_archive=str(args.output),output_sha256=sha(args.output.read_bytes()),
                  epru_entry=source_name,other_zip_entries_unchanged=True,input_archive_unchanged=True,
                  status='Offline candidate only. Import fresh patched project and verify saved/reopened stackup and actual Board BREP.')
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ['output_archive','output_sha256','physical_layer_count','total_including_masks_mm','all_non_layer_source_bytes_unchanged','status']},ensure_ascii=False))


if __name__ == '__main__':
    main()
