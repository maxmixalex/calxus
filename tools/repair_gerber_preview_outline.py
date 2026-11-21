#!/usr/bin/env python3
"""Remove Gerbonara1.6.3's duplicated closing loop from Calxus pretty SVG only.

Requires independently verified native GKO four straight+four R1 arcs. Does not
edit the Gerber archive, PCB source, copper or machining geometry.
"""
import argparse,hashlib,json,re
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('directory',type=Path);a=p.parse_args();report=json.loads((a.directory/'outline-corners.json').read_text());assert report['pass']and len(report['segments'])==8 and sum(s['kind']=='arc'for s in report['segments'])==4
changes=[]
previous={item['svg']:item for item in report.get('preview_repair',{}).get('changes',[])}
for name in ['gerber-top.svg','gerber-bottom.svg']:
 path=a.directory/name;raw=path.read_text();m=re.search(r'(<path id="outline-path" d=")([^"]+)(")',raw);assert m
 d=m[2];tokens=re.findall(r'[MLAZ]|[-+]?\d*\.?\d+(?:e[-+]?\d+)?',d);commands=[];i=0;counts={'M':2,'L':2,'A':7,'Z':0}
 while i<len(tokens):
  op=tokens[i];assert op in counts;n=counts[op];commands.append((op,tokens[i+1:i+1+n]));i+=n+1
 start=tuple(map(float,commands[0][1]));closed=None
 for idx,(op,nums) in enumerate(commands[1:],1):
  if op in ['L','A']and tuple(map(float,nums[-2:]))==start:closed=idx;break
 assert closed==8,'Unexpected preview outline: refuse to edit'
 tail=commands[closed+1:]
 if tail==[('Z',[])]:
  if name in previous:
   assert hashlib.sha256(raw.encode()).hexdigest()==previous[name]['corrected_svg_sha256']
   changes.append(previous[name])
  continue
 assert len(tail)==3 and tail[0]==commands[1] and tail[1][0]=='L'and tuple(map(float,tail[1][1]))==start and tail[2]==('Z',[]),'Unrecognized closing-loop discrepancy'
 nd=' '.join(op+(' '+' '.join(nums)if nums else'')for op,nums in commands[:closed+1]+[('Z',[])])
 original=a.directory/'diagnostics'/name.replace('.svg','.original.svg');original.parent.mkdir(exist_ok=True)
 if original.exists():assert original.read_bytes()==raw.encode(),'Original diagnostic SVG differs: refuse to overwrite'
 else:original.write_bytes(raw.encode())
 fixed=raw[:m.start(2)]+nd+raw[m.end(2):];path.write_text(fixed)
 changes.append({'svg':name,'original_svg_diagnostic':str(original.relative_to(a.directory)),'original_outline_path':d,'corrected_outline_path':nd,'original_svg_sha256':hashlib.sha256(raw.encode()).hexdigest(),'corrected_svg_sha256':hashlib.sha256(fixed.encode()).hexdigest(),'changes_only_redundant_preview_closing_loop':True})
report['preview_repair']={'scope':'Derived SVG board-fill boundary only. All four actual GKO arcs preserved, no Gerber/native file modification. Original Gerbonara contour had the first arc repeated after closure and a diagonal return.','changes':changes,'pass':True}
(a.directory/'outline-corners.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'corrected_previews':len(changes),'gerber_unchanged':True}))
