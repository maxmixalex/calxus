#!/usr/bin/env python3
"""Draw the real preserved upstream copper contact for engineering review."""
import argparse,json,hashlib
from pathlib import Path
from check_native_candidate_geometry import load,MM,LineString
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as MP
ap=argparse.ArgumentParser();ap.add_argument('archive',type=Path);ap.add_argument('--output',type=Path,required=True);args=ap.parse_args();D=load(args.archive)
ids=['517d0ae7cba763ef','b6e1148e2fb122cf'];sel=[t for t in D['lines']if t['id']in ids];shapes=[LineString([(t['x1']*MM,t['y1']*MM),(t['x2']*MM,t['y2']*MM)]).buffer(t['width']*MM/2,resolution=96)for t in sel];area=shapes[0].intersection(shapes[1]).area
fig,ax=plt.subplots(figsize=(13,7.5));fig.patch.set_facecolor('white');colors={'USB_UP_DP':'#2366a2','USB_UP_DM':'#d5622d'}
for e in D['es']:
 if 1 not in e['layers']or e['net']not in colors:continue
 if e['g'].bounds[0]>13 or e['g'].bounds[2]<4:continue
 gs=list(e['g'].geoms)if e['g'].geom_type=='MultiPolygon'else[e['g']]
 for g in gs:
  if hasattr(g,'exterior'):ax.add_patch(MP(list(g.exterior.coords),facecolor=colors[e['net']],edgecolor='none',alpha=.8))
for t in sel:ax.plot([t['x1']*MM,t['x2']*MM],[t['y1']*MM,t['y2']*MM],'--',c='#1d2428',lw=1)
for p in D['pads']:
 if p['id']in ['J1.A6','J1.A7','J1.B6','J1.B7','D1.1','D1.3','D1.4','D1.6']:ax.text(p['xy'][0],p['xy'][1]+.12,p['id'],ha='center',va='bottom',fontsize=11)
ax.annotate('Existing same-net copper contact\ncenterline separation 0.073647 mm\ntrace width 0.242095 mm',xy=(7.67,21.8),xytext=(8.9,23.1),arrowprops={'arrowstyle':'->','color':'#20252a'},bbox={'boxstyle':'round,pad=.4','fc':'#fff5e9','ec':'#c96a32'},fontsize=11)
ax.set_aspect('equal');ax.set_xlim(4.5,13.5);ax.set_ylim(19.1,24);ax.set_xlabel('Board X (mm)');ax.set_ylabel('Board Y (mm)');ax.grid(alpha=.18);ax.set_title('Preserved USB-C upstream copper: geometric self-contact',loc='left',weight='bold',fontsize=15)
fig.text(.5,.02,'Blue: USB_UP_DP   Orange: USB_UP_DM   Dashed: two original trace centerlines\nSource unchanged; this is an offline diagnostic, not a native DRC or electrical-delay signoff.',ha='center',fontsize=10);fig.tight_layout(rect=[0,.07,1,1]);args.output.parent.mkdir(parents=True,exist_ok=True);fig.savefig(args.output,dpi=180);fig.savefig(args.output.with_suffix('.svg'))
report={'schema':'calxus.frozen-hs-upstream-copper-contact.v1','source_archive_sha256':hashlib.sha256(args.archive.read_bytes()).hexdigest(),'source_line_ids':ids,'source_lines_mil':sel,'overlapping_copper_area_mm2':area,'unchanged_from_r7_baseline':True,'requires_review':True,'source_mutated':False};args.output.with_suffix('.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
