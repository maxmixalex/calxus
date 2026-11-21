#!/usr/bin/env python3
"""Promote only an independently verified instanced STEP; keep the original in tmp."""
from pathlib import Path
import gzip,hashlib,json,shutil
ROOT=Path(__file__).resolve().parent.parent


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    out=ROOT/'output';val=ROOT/'validation';temp=ROOT/'tmp';temp.mkdir(exist_ok=True)
    old_mp=val/'calxus_source_assembly-manifest.json';new_mp=val/'calxus_source_assembly_instanced-manifest.json'
    old=json.loads(old_mp.read_text());new=json.loads(new_mp.read_text())
    proof_path=val/'source-derived-assembly-instanced-roundtrip.json';proof=json.loads(proof_path.read_text())
    src=out/new['output_step_gz'];dst=out/'calxus_source_assembly.step.gz'
    assert proof['source_design_assembly_verification_pass'] and not proof['native_final_export_validated']
    assert sha(src)==new['output_step_gz_sha256']==proof['assembly_sha256']
    assert proof['assembly_manifest_sha256']==sha(new_mp)
    assert new['candidate_archive_sha256']==old['candidate_archive_sha256']
    raw=gzip.decompress(src.read_bytes())
    compression=new['gzip_compression']
    assert len(raw)==compression['uncompressed_bytes']
    assert hashlib.sha256(raw).hexdigest()==compression['uncompressed_sha256']
    assert compression['decompressed_byte_identical']
    for item in new['case_part_sources']:assert sha(out/item['path'])==item['sha256']
    prior_tag=old['output_step_gz_sha256'][:12]
    shutil.copyfile(dst,temp/f'calxus_source_assembly_prior_{prior_tag}.step.gz')
    shutil.copyfile(old_mp,temp/f'calxus_source_assembly_prior_{prior_tag}-manifest.json')
    old_report=val/'source-derived-assembly-roundtrip.json'
    old_proof=json.loads(old_report.read_text()) if old_report.exists() else None
    if old_report.exists():shutil.copyfile(old_report,temp/f'source-derived-assembly-prior_{prior_tag}-roundtrip.json')
    src.replace(dst)
    new['output_step_gz']=dst.name
    old_mp.write_text(json.dumps(new,indent=2)+'\n')
    proof['assembly']=dst.name;proof['assembly_manifest_sha256']=sha(old_mp)
    proof['exchange_representation']=new['exchange_representation']
    old_report.write_text(json.dumps(proof,indent=2)+'\n')
    evidence_path=val/'source-derived-step-instancing.json';e=json.loads(evidence_path.read_text())
    e.update(independent_roundtrip_required=False,independent_roundtrip_pass=True,
             independent_roundtrip_report=old_report.name,final_output=dst.name,
             prior_exchange_roundtrip_pass=None if old_proof is None or old_proof.get('assembly_sha256')!=old['output_step_gz_sha256'] else old_proof['source_design_assembly_verification_pass'],
             original_unshared_retained_in_scratch=True)
    evidence_path.write_text(json.dumps(e,indent=2)+'\n')
    compression_proof={'schema':'calxus.source-derived-lossless-compression.v2',
        'candidate_archive_sha256':new['candidate_archive_sha256'],
        'assembly':dst.name,'gzip_sha256':sha(dst),'gzip_bytes':dst.stat().st_size,
        **compression,'independent_gzip_crc_and_raw_sha256_verified':True,
        'geometry_changed_by_compression':False,
        'scope':'The compressor compared decompressed bytes with its exact STEP input; promotion independently checked gzip CRC, raw length and raw SHA256. No geometry or STEP text was altered by compression.'}
    (val/'source-derived-lossless-compression.json').write_text(json.dumps(compression_proof,indent=2)+'\n')
    new_mp.replace(temp/new_mp.name);proof_path.replace(temp/proof_path.name)
    print(json.dumps({'promoted':str(dst),'bytes':dst.stat().st_size,'sha256':sha(dst),'independent_roundtrip_pass':True,'removed_no_geometry':True},indent=2))


if __name__=='__main__':main()
