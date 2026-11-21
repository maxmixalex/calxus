/* Preserve current rule tables, add explicit power/USB widths and two GND planes. */
const root='D:/Works/Calc/Calxus/engineering/';
const tab=await eda.dmt_EditorControl.openDocument('2a0c39c6c6694f40');
await eda.dmt_EditorControl.activateDocument(tab);
await eda.dmt_EditorControl.waitForDocumentReady(tab);
const current=await eda.pcb_Drc.getCurrentRuleConfiguration();
const c=current.config;
c.Physics.Track.copperThickness1oz.form.data['1']={minValue:.127,defaultValue:.1524,maxValue:2.54};
const power=JSON.parse(JSON.stringify(c.Physics.Track.copperThickness1oz));
power.editName='Power500mA';power.isSetDefault=false;
power.form.data['1']={minValue:.254,defaultValue:.508,maxValue:1.016};
c.Physics.Track.Power500mA=power;
const diff=c.Physics['Differential Pair'].differentialPair.form;
diff.strokeWidthTables.data['1']={minValue:.127,defaultValue:.24209375,maxValue:.30};
diff.diffPairSpacingTables.data['1']={minValue:.1524,defaultValue:.1524,maxValue:.3048};
diff.differentailPairLenTolerMax=.254;
const via=c.Physics['Via Size'].viaSize.form;
via.viaOuterdiameterDefault=.6;via.viaInnerdiameterDefault=.3;
via.viaOuterdiameterMin=.5;via.viaInnerdiameterMin=.2;
// Pin, via and track spacing is explicitly 6 mil. These rule table values use mm.
const spacing=c.Spacing['Safe Spacing'].copperThickness1oz;
for(const table of Object.values(spacing.tables)){
  for(let i=0;i<table.content.length;i++)for(let j=0;j<table.content[i].length;j++){
    if(i<7&&j<7)table.content[i][j]=.1524;
  }
}
if(!await eda.pcb_Drc.overwriteCurrentRuleConfiguration(c))throw new Error('Rule write failed');
const netRules=await eda.pcb_Drc.getNetRules();
for(const r of netRules)if(['VBUS_IN','VBUS_NATIVE','VBUS_USBA'].includes(r.name))r.Track='Power500mA';
if(!await eda.pcb_Drc.overwriteNetRules(netRules))throw new Error('Net rules write failed');
const state=JSON.parse(await(await eda.sys_FileSystem.readFileFromFileSystem(root+'pcb-build-state.json')).text());
state.planes=state.planes||{};
const nativePours=await eda.pcb_PrimitivePour.getAll();
for(const layer of [15,16]){
  // Cached IDs can disappear on reload. Resolve against actual GND pour objects.
  const candidates=nativePours.filter(p=>p.getState_Layer()===layer&&p.getState_Net()==='GND');
  const cached=candidates.find(p=>p.getState_PrimitiveId()===state.planes[layer]);
  if(!cached&&candidates.length>1)throw new Error('Ambiguous GND pours on layer '+layer);
  let pour=cached||candidates[0];
  // Y-up canvas: R origin is top-left (0.5,41.5), with positive height down.
  const p=eda.pcb_MathPolygon.createPolygon(['R',.5/.0254,41.5/.0254,79/.0254,41/.0254,0,.5/.0254]);
  const name='GND_L'+(layer===15?2:3);
  pour=pour?await eda.pcb_PrimitivePour.modify(pour,{net:'GND',layer,complexPolygon:p,pourFillMethod:'solid',preserveSilos:false,pourName:name,pourPriority:0,lineWidth:.1/.0254,primitiveLock:true}):
    await eda.pcb_PrimitivePour.create('GND',layer,p,'solid',false,name,0,.1/.0254,true);
  if(!pour)throw new Error('Ground plane update failed for layer '+layer);
  state.planes[layer]=pour.getState_PrimitiveId();
}
const filled=await eda.pcb_PrimitivePour.rebuildAllCopperRegions();
const nativeSaved=await eda.pcb_Document.save();
const source=await eda.sys_FileManager.getDocumentSource();
let inBoard=false;const actualPours=new Map();
for(const row of source.split(/\r?\n/)){
  if(!row.trim())continue;const cut=row.indexOf('||');if(cut<0)throw new Error('Unsupported native source record');
  const h=JSON.parse(row.slice(0,cut)),body=row.slice(cut+2).replace(/\|$/,'');const d=body?JSON.parse(body):null;
  if(h.type==='DOCHEAD'){inBoard=d?.uuid==='2a0c39c6c6694f40';continue;}
  if(inBoard&&h.type==='POUR'){if(d===null)actualPours.delete(h.id);else actualPours.set(h.id,d);}
}
function rectangle(path){if(!Array.isArray(path))return undefined;if(path[0]==='R')return path;for(const child of path){const r=rectangle(child);if(r)return r;}}
const near=(a,b)=>Number.isFinite(Number(a))&&Math.abs(Number(a)-b)<.02;
for(const layer of [15,16]){
  const d=actualPours.get(state.planes[layer]),r=rectangle(d?.path);
  if(!d||d.layerId!==layer||d.netName!=='GND'||!r||!near(r[1],.5/.0254)||!near(r[2],41.5/.0254)||!near(r[3],79/.0254)||!near(r[4],41/.0254))throw new Error('Plane positive-Y readback failed on layer '+layer);
}
await eda.sys_FileSystem.saveFileToFileSystem(root+'pcb-build-state.json',new Blob([JSON.stringify(state,null,2)]));
// This is raw native source, not a zipped epro2 project archive.
await eda.sys_FileSystem.saveFileToFileSystem(root+'pcb-after-rules-live.epcb2',new Blob([source]));
const after=await eda.pcb_Drc.getCurrentRuleConfiguration();
await eda.sys_FileSystem.saveFileToFileSystem(root+'pcb-rules-final.json',new Blob([JSON.stringify(after,null,2)]));
return {nativeSaved,planes:state.planes,filledGroups:filled.length,positiveYGeometryVerified:true,powerNets:netRules.filter(r=>r.Track==='Power500mA').map(r=>r.name),
  differential:after.config.Physics['Differential Pair'].differentialPair.form};
