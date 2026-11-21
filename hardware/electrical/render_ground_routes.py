"""Render planned USB routing over actual pad polygons for engineering review."""
import json,sys
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as MP, Circle
try:import shapely
except ImportError:sys.path.insert(0,'/tmp/calxus_deps');import shapely
from shapely.geometry import box
from shapely.affinity import rotate,translate
P=Path(__file__).parent;E=P.parent/'evidence'
R=json.loads((P/'combined_planned_copper.json').read_text());R['tracks']=R['lines'];A=json.loads((E/'pcb-components-pads-r5-planned.json').read_text());D=json.loads((P/'calxus_design_input.json').read_text());C=json.loads((E/'eda_parts_catalog_full.json').read_text());refs={p['ref']:p for p in D['parts']}
colors={'USB_UP_DP':'#0072B2','USB_UP_DM':'#56B4E9','USB_NATIVE_DP':'#009E73','USB_NATIVE_DM':'#8CCF89','USB_A_DP':'#D55E00','USB_A_DM':'#E69F00','GND':'#333333'}
fig,axs=plt.subplots(2,2,figsize=(16,12),layout='constrained')
for ax,window,title in zip(axs.flat,[(0,80,0,42),(44.5,52,21.5,29),(57,63,8,13),(37,43,9,14)],['All USB + local GND routes','TUSB3410 / EP vias','CH343P / EP vias','USB-A ESD / EEPROM bypass']):
 for c in A['components']:
  lib={p['padNumber']:p for p in C[refs[c['ref']]['lcsc']]['footprint']['pads']}
  visible=False
  for p in c['pads']:
   q=lib[p['number']];g=box(-q['width']/2,-q['height']/2,q['width']/2,q['height']/2);g=rotate(g,c['rotation']+q['rotation'],origin=(0,0));g=translate(g,p['x'],p['y']);pts=np.array(g.exterior.coords)*.0254
   ax.add_patch(MP(pts,facecolor=colors.get(p.get('net'),'#d8d8d8'),edgecolor='#666666',linewidth=.3,alpha=.65))
  x,y=c['x']*.0254,c['y']*.0254
  if window[0]<x<window[1] and window[2]<y<window[3]:ax.text(x,y,c['ref'],fontsize=5,color='#333333',ha='center')
 for t in R['tracks']:
  ax.plot([t['x1']*.0254,t['x2']*.0254],[t['y1']*.0254,t['y2']*.0254],color=colors[t['net']],lw=1.6 if title.startswith('All') else 2.6,linestyle='-' if t['layer']==1 else '--',zorder=4)
 for v in R['vias']:
  ax.add_patch(Circle((v['x']*.0254,v['y']*.0254),v['diameter']*.0254/2,edgecolor=colors[v['net']],facecolor='white',linewidth=1,zorder=5));ax.add_patch(Circle((v['x']*.0254,v['y']*.0254),v['holeDiameter']*.0254/2,color='#333333',zorder=6))
 ax.set(xlim=window[:2],ylim=window[2:],aspect='equal',title=title,xlabel='X (mm)',ylabel='Y (mm)');ax.grid(alpha=.15)
fig.suptitle('Calxus r5 — solid: L1, dashed: L4; physical pad positions; line widths illustrative',fontsize=15)
fig.savefig(P/'ground_routes_review.png',dpi=180)
