"""Finalize the lean, Git-tracked mechanical deliverables without a duplicate ZIP.

CAD geometry is not modified. Raster images embedded in the vector PDF are
compressed once; all dimensions, vectors, text and embedded fonts are preserved.
"""
from pathlib import Path
import hashlib, io, json
import fitz
from PIL import Image

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'output'
PDF=OUT/'calxus_mechanical_drawing.pdf'

def optimize_pdf():
    if not PDF.exists(): return
    before=PDF.stat().st_size
    doc=fitz.open(PDF)
    original_text=[p.get_text() for p in doc]
    seen=set();changed=False
    for page in doc:
        for item in page.get_images(full=True):
            xref=item[0]
            if xref in seen: continue
            seen.add(xref)
            if 'DCTDecode' in doc.xref_get_key(xref,'Filter')[1]: continue
            raw=doc.extract_image(xref)
            im=Image.open(io.BytesIO(raw['image'])).convert('RGB')
            encoded=io.BytesIO();im.save(encoded,format='JPEG',quality=90,subsampling=0,optimize=True)
            page.replace_image(xref,stream=encoded.getvalue());changed=True
    if changed:
        temp=PDF.with_suffix('.optimized.pdf')
        doc.save(temp,garbage=4,deflate=True);doc.close()
        with fitz.open(temp) as check:
            assert [p.get_text() for p in check]==original_text, 'PDF text changed unexpectedly'
        temp.replace(PDF)
    else: doc.close()
    print(f'PDF: {before:,} -> {PDF.stat().st_size:,} bytes')

def manifest():
    files=[]
    allowed_root={'.gitignore','README.md','requirements.txt','mechanical_contract.json','generate_mechanical.py','assemble_actual_pcba.py','assemble_source_pcba.py','blender_render.py','export_freecad.py','make_release.py'}
    for path in sorted(ROOT.rglob('*')):
        if not path.is_file(): continue
        rel=path.relative_to(ROOT)
        if len(rel.parts)==1 and path.name not in allowed_root: continue
        if len(rel.parts)>1 and rel.parts[0] not in {'output','validation'}: continue
        if '__pycache__' in rel.parts or path.suffix.lower()=='.pyc': continue
        if path.name=='artifact_manifest.json' or path.suffix.lower() in {'.zip','.blend','.blend1','.fcbak','.fcstd1'}: continue
        files.append({'path':str(rel),'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    contract=json.loads((ROOT/'mechanical_contract.json').read_text())
    record={'revision':contract['revision'],'scope':'Lean mechanical prototype package. STEP uses assembly coordinates; STL uses print orientation. Physical fit has not been tested.','files':files}
    (OUT/'artifact_manifest.json').write_text(json.dumps(record,indent=2)+'\n')
    total=sum(f['bytes'] for f in files)+(OUT/'artifact_manifest.json').stat().st_size
    print(f'{len(files)+1} retained files; {total:,} bytes ({total/1024**2:.2f} MiB)')

if __name__=='__main__':
    optimize_pdf()
    manifest()
