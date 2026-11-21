#!/usr/bin/env python3
"""Losslessly compress STEP bytes; never change their geometry or text.

Optional installed libdeflate uses its documented C API at level12. Standard
Python gzip level9 is a portable fallback. Either output is independently
decompressed and compared byte-for-byte before it can be used.
API: https://github.com/ebiggers/libdeflate/blob/master/libdeflate.h
"""
from pathlib import Path
import ctypes,ctypes.util,gzip,hashlib,json,shutil


def compress_step(raw):
    name=ctypes.util.find_library('deflate')
    if name:
        lib=ctypes.CDLL(name)
        lib.libdeflate_alloc_compressor.argtypes=[ctypes.c_int];lib.libdeflate_alloc_compressor.restype=ctypes.c_void_p
        lib.libdeflate_gzip_compress_bound.argtypes=[ctypes.c_void_p,ctypes.c_size_t];lib.libdeflate_gzip_compress_bound.restype=ctypes.c_size_t
        lib.libdeflate_gzip_compress.argtypes=[ctypes.c_void_p,ctypes.c_void_p,ctypes.c_size_t,ctypes.c_void_p,ctypes.c_size_t];lib.libdeflate_gzip_compress.restype=ctypes.c_size_t
        lib.libdeflate_free_compressor.argtypes=[ctypes.c_void_p];lib.libdeflate_free_compressor.restype=None
        c=lib.libdeflate_alloc_compressor(12)
        if not c:raise MemoryError('libdeflate compressor allocation failed')
        try:
            n=lib.libdeflate_gzip_compress_bound(c,len(raw));out=ctypes.create_string_buffer(n);src=ctypes.create_string_buffer(raw)
            size=lib.libdeflate_gzip_compress(c,src,len(raw),out,n)
            if not size:raise ValueError('Compression exceeded the documented bound')
            blob=out.raw[:size]
        finally:lib.libdeflate_free_compressor(c)
        method='libdeflate level12, standard gzip format'
    else:
        blob=gzip.compress(raw,compresslevel=9,mtime=0);method='Python gzip level9 fallback'
    if gzip.decompress(blob)!=raw:raise ValueError('Lossless compression roundtrip failed')
    return blob,{'method':method,'uncompressed_bytes':len(raw),'uncompressed_sha256':hashlib.sha256(raw).hexdigest(),'decompressed_byte_identical':True}


def main():
    root=Path(__file__).resolve().parent.parent;val=root/'validation';out=root/'output';temp=root/'tmp';temp.mkdir(exist_ok=True)
    mp=val/'calxus_source_assembly-manifest.json';m=json.loads(mp.read_text());p=out/m['output_step_gz']
    old=p.read_bytes();raw=gzip.decompress(old);blob,compression=compress_step(raw)
    oldsha=hashlib.sha256(old).hexdigest();newsha=hashlib.sha256(blob).hexdigest()
    if oldsha!=m['output_step_gz_sha256']:raise ValueError('Assembly hash does not match manifest')
    shutil.copyfile(p,temp/'calxus_source_assembly_zlib_before_lossless_recompression.step.gz')
    p.write_bytes(blob);m['output_step_gz_sha256']=newsha;m['gzip_compression']=compression
    mp.write_text(json.dumps(m,indent=2)+'\n')
    proof={'geometry_changed':False,'old_gzip_sha256':oldsha,'new_gzip_sha256':newsha,'old_bytes':len(old),'new_bytes':len(blob),**compression}
    report=val/'source-derived-assembly-roundtrip.json';r=json.loads(report.read_text())
    assert r['assembly_sha256']==oldsha and r['source_design_assembly_verification_pass']
    r['geometry_readback_gzip_sha256']=oldsha;r['assembly_sha256']=newsha;r['compression_only_recheck']=proof
    r['assembly_manifest_sha256']=hashlib.sha256(mp.read_bytes()).hexdigest();report.write_text(json.dumps(r,indent=2)+'\n')
    epath=val/'source-derived-step-instancing.json';e=json.loads(epath.read_text());e['instanced_step_gz_sha256']=newsha;e['instanced_step_gz_bytes']=len(blob);e['lossless_gzip_compression']=compression;epath.write_text(json.dumps(e,indent=2)+'\n')
    (val/'source-derived-lossless-compression.json').write_text(json.dumps(proof,indent=2)+'\n');print(json.dumps(proof,indent=2))


if __name__=='__main__':main()
