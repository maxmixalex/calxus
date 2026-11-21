/* Read-only native copper/pad/paste-source audit export.
 * Run in the PCB after applying reviewed USB and GND copper.
 * Writes four engineering JSON snapshots; does not create/modify PCB primitives.
 * Returns only file sizes/counts, never complete source contents.
 */
const ROOT='D:/Works/Calc/Calxus/engineering/';
const PCB='2a0c39c6c6694f40';
const beganAt=new Date().toISOString();
const expectedFootprints={
  U2:'dc96823453a64dbcb382e28438ab8b56',
  U3:'c75e883c09144668b0613740ff1e4391'
};
async function read(name){
  const f=await eda.sys_FileSystem.readFileFromFileSystem(ROOT+name);
  if(!f)throw new Error('Missing '+name);
  const d=JSON.parse(await f.text());
  if(d?.success===false&&d.code)throw new Error('Read failed '+name+': '+d.message);
  return d;
}
async function save(name,data){
  const text=JSON.stringify(data,null,2);
  const blob=new Blob([text],{type:'application/json'});
  if(!await eda.sys_FileSystem.saveFileToFileSystem(ROOT+name,blob))throw new Error('Save failed '+name);
  const f=await eda.sys_FileSystem.readFileFromFileSystem(ROOT+name);
  if(!f||await f.text()!==text)throw new Error('Readback differs '+name);
  return {name,bytes:blob.size};
}
function finite(value,label){
  if(typeof value!=='number'||!Number.isFinite(value))throw new Error('Invalid '+label);
  return value;
}
function padData(p){
  const shape=p.getState_Pad();
  const out={
    id:p.getState_PrimitiveId(),number:String(p.getState_PadNumber()),
    net:p.getState_Net()||'',layer:p.getState_Layer(),
    x:finite(p.getState_X(),'pad x'),y:finite(p.getState_Y(),'pad y'),
    rotation:p.getState_Rotation(),pad:shape,
    specialPad:p.getState_SpecialPad(),hole:p.getState_Hole(),
    holeOffsetX:p.getState_HoleOffsetX(),holeOffsetY:p.getState_HoleOffsetY(),
    holeRotation:p.getState_HoleRotation(),metallization:p.getState_Metallization(),
    padType:p.getState_PadType(),mask:p.getState_SolderMaskAndPasteMaskExpansion()
  };
  if(Array.isArray(shape)&&typeof shape[1]==='number'&&typeof shape[2]==='number'){
    out.shape=shape[0];out.width=shape[1];out.height=shape[2];
    if(shape[0]==='ELLIPSE'&&Math.abs(shape[1]-shape[2])<.001)out.diameter=shape[1];
  }
  return out;
}
const tab=await eda.dmt_EditorControl.openDocument(PCB);
await eda.dmt_EditorControl.activateDocument(tab);
if(!await eda.dmt_EditorControl.waitForDocumentReady(tab))throw new Error('PCB not ready');
const state=await read('pcb-build-state.json');
if(!state.testpads||Object.keys(state.testpads).length!==23)throw new Error('Expected23 test-pad IDs in build state');
const [nativeLines,nativeVias,nativeComponents]=await Promise.all([
  eda.pcb_PrimitiveLine.getAll(),eda.pcb_PrimitiveVia.getAll(),eda.pcb_PrimitiveComponent.getAll()
]);
if(nativeComponents.length!==97)throw new Error('Expected97 components, got '+nativeComponents.length);
const lines=nativeLines.map(p=>({
  id:p.getState_PrimitiveId(),net:p.getState_Net()||'',layer:p.getState_Layer(),
  x1:p.getState_StartX(),y1:p.getState_StartY(),x2:p.getState_EndX(),y2:p.getState_EndY(),
  width:p.getState_LineWidth(),locked:p.getState_PrimitiveLock()
}));
const vias=nativeVias.map(p=>({
  id:p.getState_PrimitiveId(),net:p.getState_Net()||'',
  x:p.getState_X(),y:p.getState_Y(),diameter:p.getState_Diameter(),
  holeDiameter:p.getState_HoleDiameter(),viaType:p.getState_ViaType(),
  mask:p.getState_SolderMaskExpansion(),locked:p.getState_PrimitiveLock()
}));
for(const t of lines)for(const k of ['layer','x1','y1','x2','y2','width'])finite(t[k],'line '+k);
for(const v of vias)for(const k of ['x','y','diameter','holeDiameter'])finite(v[k],'via '+k);
const copper={schema:'calxus.native-copper-audit.v1',units:'mil',pcbId:PCB,beganAt,
  exportedAt:new Date().toISOString(),lines,vias,
  scope:'All native line and via primitives, without net filtering. Polygon/pour/arc copper is not included; review exported Gerber/native DRC separately.'};
const files=[await save('native-copper-audit.json',copper)];
const [nativePours,stackup,documentSource,layerItems]=await Promise.all([
  eda.pcb_PrimitivePour.getAll(),eda.pcb_Layer.getStackup(),eda.sys_FileManager.getDocumentSource(),
  eda.pcb_Layer.getAllLayers()
]);
const pours=await Promise.all(nativePours.map(async p=>{
  const out={id:p.getState_PrimitiveId(),net:p.getState_Net()||'',layer:p.getState_Layer(),
    name:p.getState_PourName(),fillMethod:p.getState_PourFillMethod(),
    preserveSilos:p.getState_PreserveSilos(),priority:p.getState_PourPriority(),
    lineWidth:p.getState_LineWidth(),locked:p.getState_PrimitiveLock(),
    complexPolygon:p.getState_ComplexPolygon().getSource()};
  const poured=await p.getCopperRegion();
  out.hasPouredRegion=poured!==undefined;
  if(poured){
    out.pouredId=poured.getState_PrimitiveId();
    out.pouredLayer=poured.getState_Layer();
    out.pouredParentId=poured.getState_PourPrimitiveId();
    out.fills=poured.getState_PourFills().map(f=>({id:f.id,fill:f.fill,lineWidth:f.lineWidth,path:f.path.getSource()}));
    out.fillCount=out.fills.length;
    out.enabledFillCount=out.fills.filter(f=>f.fill).length;
  }
  return out;
}));
const sourceRecordsNative=String(documentSource).split(/\r?\n/).filter(line=>
  /^\[\s*"(?:LAYER|POUR|POURED|COPPER|PHYSICAL)/.test(line)||
  /^\{\s*"type"\s*:\s*"(?:LAYER|POUR|POURED|COPPER|PHYSICAL)/.test(line));
files.push(await save('native-planes-audit.json',{
  schema:'calxus.native-planes-audit.v1',units:'mil',pcbId:PCB,beganAt,
  exportedAt:new Date().toISOString(),pours,stackup,layerItems,sourceRecords:sourceRecordsNative,
  expectedPlaneIds:state.planes||{},
  scope:'Actual Pour objects and physical stackup plus matching original LAYER/POUR/POURED/COPPER/PHYSICAL source records. A boundary alone does not establish filled copper or continuity; verify poured geometry/Gerber. No rebuild or edits performed.'
}));
const components=[];
for(let start=0;start<nativeComponents.length;start+=8){
  const batch=await Promise.all(nativeComponents.slice(start,start+8).map(async c=>{
    const ps=await eda.pcb_PrimitiveComponent.getAllPinsByPrimitiveId(c.getState_PrimitiveId());
    if(!Array.isArray(ps))throw new Error('No native pads '+c.getState_Designator());
    return {ref:c.getState_Designator(),id:c.getState_PrimitiveId(),
      x:c.getState_X(),y:c.getState_Y(),rotation:c.getState_Rotation(),layer:c.getState_Layer(),
      footprint:c.getState_Footprint(),pads:ps.map(padData)};
  }));
  components.push(...batch);
}
components.sort((a,b)=>a.ref.localeCompare(b.ref,undefined,{numeric:true}));
// Component-pad getState_Hole()/offset/angle have inconsistent conversion in
// this native API build. Retain those API values as evidence, but independently
// attach exact project footprint PAD source geometry for J2 manufacture/routing.
const j2=components.find(c=>c.ref==='J2');
if(j2?.footprint?.name==='USB-A-TH_AF-10.0-HC6.3'){
  const src=await eda.lib_Footprint.getDocumentSource(j2.footprint.uuid,j2.footprint.libraryUuid);
  const records=[];for(const raw of String(src).split('\n')){if(!raw.startsWith('{"type":"PAD"'))continue;const i=raw.indexOf('||');const h=JSON.parse(raw.slice(0,i)),d=JSON.parse(raw.slice(i+2).replace(/\|\s*$/,''));records.push({id:h.id,...d});}
  if(records.length!==6)throw new Error('J2 exact source must contain six pads');
  j2.authoritativeFootprintPadSource={units:'mil',footprintUuid:j2.footprint.uuid,records,
    note:'Use source hole dimensions and relativeAngle. API hole/offset/angle values above are retained unaltered and must not be interpreted as manufacturing sizes. Signal holes ROUND39.37mil; shield slots82.677x31.496mil,relativeAngle90. Final Excellon verification required.'};
}
const testpads=[];
const entries=Object.entries(state.testpads).sort((a,b)=>a[0].localeCompare(b[0],undefined,{numeric:true}));
for(let start=0;start<entries.length;start+=8){
  const batch=await Promise.all(entries.slice(start,start+8).map(async([ref,id])=>{
    const p=await eda.pcb_PrimitivePad.get(id);
    if(!p)throw new Error('Missing actual test pad '+ref+' '+id);
    const out={ref,...padData(p)};
    if(out.number!==ref)throw new Error('Test-pad number differs '+ref+' vs '+out.number);
    if(out.diameter===undefined)throw new Error('Expected circular test-pad geometry '+ref);
    return out;
  }));
  testpads.push(...batch);
}
const pads={schema:'calxus.native-pads-audit.v1',units:'mil',pcbId:PCB,beganAt,
  exportedAt:new Date().toISOString(),components,testpads,
  scope:'Fresh native component pin and PCB-only test-pad position/shape/net/mask data; no placement inferred from design JSON.'};
files.push(await save('native-pads-audit.json',pads));
const allSources=await eda.sys_FileManager.getDocumentFootprintSources();
if(!Array.isArray(allSources))throw new Error('Invalid document footprint sources');
const sourceRecords=[];
for(const [ref,expected]of Object.entries(expectedFootprints)){
  const c=components.find(x=>x.ref===ref);
  if(!c)throw new Error('Missing '+ref);
  const actual=c.footprint?.uuid||expected;
  let item=allSources.find(s=>s.footprintUuid===actual)||allSources.find(s=>s.footprintUuid===expected);
  let sourceMethod='sys_FileManager.getDocumentFootprintSources';
  if(!item){
    const documentSource=await eda.lib_Footprint.getDocumentSource(actual,c.footprint?.libraryUuid);
    if(typeof documentSource!=='string'||!documentSource.length)throw new Error('Missing native footprint source '+ref);
    item={footprintUuid:actual,documentSource};
    sourceMethod='lib_Footprint.getDocumentSource fallback';
  }
  const ep=c.pads.find(p=>p.number===(ref==='U2'?'33':'17'));
  if(!ep)throw new Error('Missing native EP '+ref);
  sourceRecords.push({ref,expectedFootprintUuid:expected,actualFootprint:c.footprint,
    footprintUuid:item.footprintUuid,sourceMethod,documentSource:item.documentSource,epPad:ep,
    placement:{x:c.x,y:c.y,rotation:c.rotation,layer:c.layer}});
}
files.push(await save('qfn-footprint-sources.json',{
  schema:'calxus.qfn-footprint-sources.v1',units:'mil',pcbId:PCB,beganAt,
  exportedAt:new Date().toISOString(),documentFootprintCount:allSources.length,
  sources:sourceRecords,
  scope:'Exact current-document footprint source first; explicit library fallback only if not returned. No paste primitives created or modified.'
}));
return {files,counts:{lines:lines.length,vias:vias.length,components:components.length,
  componentPads:components.reduce((n,c)=>n+c.pads.length,0),testpads:testpads.length,
  qfnSources:sourceRecords.length,pours:pours.length,planeSourceRecords:sourceRecordsNative.length},beganAt,completedAt:new Date().toISOString()};
