"""Run with freecadcmd export_freecad.py; STEP exchange assembly is the source of features.
The parametric source is generate_mechanical.py + mechanical_contract.json.
"""
import os,json
import FreeCAD as App
import Part
root=os.path.dirname(os.path.abspath(__file__))
out=os.path.join(root,'output')
c=json.load(open(os.path.join(root,'mechanical_contract.json')))
doc=App.newDocument('Calxus_R1')
for stem in ['calxus_base','calxus_lid','calxus_comb_lower_tpu','calxus_comb_upper_tpu','calxus_slider_fork','calxus_slider_thumb','calxus_pcb_reference']:
 shape=Part.Shape();shape.read(os.path.join(out,stem+'.step'))
 if 'slider_' in stem:shape.translate(App.Vector(c['selector']['assembly_display_position_offset'],0,0))
 ob=doc.addObject('PartDesign::Feature',stem);ob.Label=stem.replace('calxus_','').replace('_',' ').title();ob.Shape=shape
 ob.addProperty('App::PropertyString','SourceContract','Design').SourceContract='mechanical_contract.json'
 ob.addProperty('App::PropertyString','Revision','Design').Revision=c['revision']
 ob.addProperty('App::PropertyString','RebuildCommand','Design').RebuildCommand='python generate_mechanical.py'
 ob.addProperty('App::PropertyBool','GeometryValid','Validation').GeometryValid=shape.isValid()
 ob.addProperty('App::PropertyVolume','SolidVolume','Validation').SolidVolume=shape.Volume
sheet=doc.addObject('Spreadsheet::Sheet','Interface')
rows=[['CALXUS MECHANICAL CONTRACT','Value','Units'],['Revision',c['revision'],''],['PCB length','80','mm'],['PCB width','42','mm'],['PCB thickness','1.6','mm'],['Case length','86','mm'],['Case width','48','mm'],['Case body height','19','mm'],['Total incl thumb','21.9','mm'],['Thumb outer size','7.0 x 6.0','mm'],['Fork calibration','-0.35 to +0.35','mm'],['USB-A front projection','1.925','mm'],['Mount holes','2.2','mm'],['Mount keepout radius','3.0','mm'],['Mini/TI/Casio jacket','3.8','mm'],['Mini/TI/Casio bore','3.6','mm'],['AUX prepared sleeve','2.9 to 3.1','mm'],['AUX bore','2.8','mm'],['Origin','PCB lower-left, bottom',''],['Source','mechanical_contract.json',''],['Status','Prototype; physical fit not tested','']]
for r,row in enumerate(rows,1):
 for col,value in enumerate(row):sheet.set(chr(65+col)+str(r),value)
sheet.setColumnWidth('A',190);sheet.setColumnWidth('B',260);sheet.setColumnWidth('C',60)
doc.recompute();doc.saveAs(os.path.join(out,'calxus_enclosure.FCStd'))
print('Saved native FreeCAD assembly:',os.path.join(out,'calxus_enclosure.FCStd'))
App.closeDocument(doc.Name)
