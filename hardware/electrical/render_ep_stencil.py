"""Render the explicitly provisional EP aperture proposal, not native PCB proof."""
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, FancyBboxPatch, Patch

P=Path(__file__).resolve().parent
D=json.loads((P/'ep_stencil_proposal.json').read_text())
fig,axes=plt.subplots(1,2,figsize=(11.5,7.6))
fig.subplots_adjust(left=.07,right=.96,top=.81,bottom=.34,wspace=.30)
fig.suptitle('QFN exposed-pad stencil proposal',fontsize=20,y=.96,weight='bold')
fig.text(.5,.90,'Proposed geometry only — verify existing native apertures before applying',ha='center',fontsize=11,color='#995500')
for ax,c in zip(axes,D['components']):
    w,h=c['copper_size_mm']
    ax.add_patch(Rectangle((-w/2,-h/2),w,h,facecolor='#fff1d2',edgecolor='#b66b00',lw=1.5))
    for window in c['windows']:
        x,y=window['center_relative_to_actual_EP_mm'];ww=window['width_mm'];hh=window['height_mm'];r=window['corner_radius_mm']
        ax.add_patch(FancyBboxPatch((x-ww/2,y-hh/2),ww,hh,boxstyle=f'round,pad=0,rounding_size={r}',facecolor='#5ba8ce',edgecolor='#1f5d7a',lw=1))
    lim=w/2+.25
    ax.set(xlim=(-lim,lim),ylim=(-lim,lim),aspect='equal',xlabel='Relative X (mm)',ylabel='Relative Y (mm)')
    ax.set_title(f"{c['reference']} · {c['mpn']}",fontsize=14,pad=12)
    ax.axhline(0,lw=.5,color='#999999',ls=':');ax.axvline(0,lw=.5,color='#999999',ls=':')
    ax.grid(alpha=.15)
    wi=c['windows'][0]
    text=(f"Copper {w:.2f} × {h:.2f} mm\n4 windows {wi['width_mm']:.2f} × {wi['height_mm']:.2f} mm, R{wi['corner_radius_mm']:.2f}\n"
          f"Steel web {c['web_mm']:.2f} mm · coverage {c['coverage_of_actual_copper_percent']:.3f}%")
    ax.text(.5,-.24,text,transform=ax.transAxes,va='top',ha='center',fontsize=11,linespacing=1.6)
fig.legend(handles=[Patch(facecolor='#fff1d2',edgecolor='#b66b00',label='Existing exposed copper'),Patch(facecolor='#5ba8ce',edgecolor='#1f5d7a',label='Proposed paste aperture')],loc='lower center',bbox_to_anchor=(.5,.035),ncol=2,frameon=False)
fig.text(.5,.014,'U2: TI RHB0032E stencil example. U3: project choice using generic QFN guidance. Four EP vias require VIPPO.',ha='center',fontsize=9,color='#555555')
fig.savefig(P/'ep_stencil_review.svg')
fig.savefig(P/'ep_stencil_review.png',dpi=160)
