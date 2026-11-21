#!/usr/bin/env python3
"""Draw exact saved native copper for the reviewed USB-C upstream remedy."""
import argparse,hashlib,json
from pathlib import Path
from check_native_candidate_geometry import load,Point
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as MP,Circle
ap=argparse.ArgumentParser();ap.add_argument('archive',type=Path);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args();D=load(a.archive)
fig,ax=plt.subplots(figsize=(13,8));colors={'USB_UP_DP':'#2166ac','USB_UP_DM':'#d95f32','VBUS_IN':'#b48613'}
for e in D['es']:
 if 1 not in e['layers']or not e['g'].intersects(Point(9.1,21).buffer(4.7)):continue
 color=colors.get(e['net'],'#aeb8bf');g=e['g'];parts=list(g.geoms)if hasattr(g,'geoms')else[g]
 for q in parts:
  if hasattr(q,'exterior'):ax.add_patch(MP(list(q.exterior.coords),facecolor=color,edgecolor='none',alpha=.84 if e['net']in colors else .55));[ax.add_patch(MP(list(r.coords),facecolor='white',edgecolor='none'))for r in q.interiors]
for p in D['pads']:
 if p['id']in['J1.A6','J1.A7','J1.B6','J1.B7','D1.1','D1.3','D1.4','D1.5','D1.6']:ax.text(p['xy'][0]-.03,p['xy'][1]+.16,p['id'],ha='center',fontsize=10)
ax.annotate('Ordinary VBUS via\n(8.55,20.64), outer0.5 / hole0.2 mm',xy=(8.55,20.64),xytext=(10.2,19.6),arrowprops={'arrowstyle':'->'},bbox={'fc':'white','ec':'#b48613','boxstyle':'round,pad=.35'},fontsize=10)
ax.set_xlim(5.25,13.25);ax.set_ylim(19.25,23.5);ax.set_aspect('equal');ax.set_xlabel('Board X (mm)');ax.set_ylabel('Board Y (mm)');ax.grid(alpha=.15);ax.set_title('Reviewed USB-C upstream copper — both connector orientations',loc='left',weight='bold',fontsize=15)
fig.text(.5,.025,'Blue DP · orange DM · ochre VBUS · gray other copper/NC pads\nExact saved-source shapes; trace/via geometry review, separate from actual native DRC and CAM.',ha='center',fontsize=10)
fig.tight_layout(rect=[0,.07,1,1]);a.output.parent.mkdir(parents=True,exist_ok=True);fig.savefig(a.output,dpi=180);plt.close(fig)
a.output.with_suffix('.json').write_text(json.dumps({'source_archive_sha256':hashlib.sha256(a.archive.read_bytes()).hexdigest(),'scope':'Exact L1 copper from saved source; all foreign/NC obstacles displayed','image_sha256':hashlib.sha256(a.output.read_bytes()).hexdigest()},indent=2)+'\n')
