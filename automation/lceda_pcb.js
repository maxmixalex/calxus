/* Calxus PCB construction in the user's native JLCEDA project.
 * Input coordinates are mm; PCB API coordinates are mil with Y up.
 * Polygon R starts at the upper-left corner and its positive height extends down.
 * args.stage: import | layout | pads | rules | export
 */
const ROOT='D:/Works/Calc/Calxus/engineering/';
const args=__CLI__.args||{};
const mm=n=>n/0.0254;
async function read(name,fallback){const f=await eda.sys_FileSystem.readFileFromFileSystem(ROOT+name);if(!f)return fallback;const d=JSON.parse(await f.text());if(d?.success===false&&d.code)return fallback;return d;}
async function write(name,obj){if(!await eda.sys_FileSystem.saveFileToFileSystem(ROOT+name,new Blob([JSON.stringify(obj,null,2)],{type:'application/json'})))throw new Error('Save '+name+' failed');}
const design=await read('design-input.json');
const pcbId='2a0c39c6c6694f40';
const schematicId='992d265f851ac884';
const state=await read('pcb-build-state.json',{testpads:{},holes:[],regions:[],pairs:[]});
state.testpads=state.testpads||{};state.holes=state.holes||[];
state.regions=state.regions||[];state.pairs=state.pairs||[];
const idOf=p=>p.getState_PrimitiveId();
const near=(a,b)=>Number.isFinite(Number(a))&&Math.abs(Number(a)-b)<.02;
function one(items,label){if(items.length>1)throw new Error('Ambiguous native primitives for '+label);return items[0];}
function findPath(path,kind){
  if(!Array.isArray(path))return undefined;
  if(path[0]===kind)return path;
  for(const child of path){const found=findPath(child,kind);if(found)return found;}
}
async function boardRecords(){
  const source=await eda.sys_FileManager.getDocumentSource();
  const records=new Map();let active=false,found=false;
  for(const row of source.split(/\r?\n/)){
    if(!row.trim())continue;const cut=row.indexOf('||');if(cut<0)throw new Error('Unsupported native source record');
    const h=JSON.parse(row.slice(0,cut)),body=row.slice(cut+2).replace(/\|$/,'');
    const d=body?JSON.parse(body):null;
    if(h.type==='DOCHEAD'){active=d?.uuid===pcbId;if(active)found=true;continue;}
    if(active){const key=h.type+':'+h.id;if(d===null)records.delete(key);else records.set(key,d);}
  }
  if(!found)throw new Error('Active source is not the expected PCB '+pcbId);
  return records;
}
const tab=await eda.dmt_EditorControl.openDocument(pcbId);
await eda.dmt_EditorControl.activateDocument(tab);
if(!await eda.dmt_EditorControl.waitForDocumentReady(tab))throw new Error('PCB not ready');
if(args.stage==='import'){
  const imported=await eda.pcb_Document.importChanges(schematicId,true);
  if(!imported)throw new Error('Schematic import failed');
  await eda.pcb_Layer.setTheNumberOfCopperLayers(4);
  await eda.dmt_Pcb.modifyPcbName(pcbId,'Calxus_RevA');
  await eda.pcb_Document.save();
  const components=await eda.pcb_PrimitiveComponent.getAll();
  return {imported,count:components.length,refs:components.map(c=>c.getState_Designator())};
}
if(args.stage==='layout'){
  const components=await eda.pcb_PrimitiveComponent.getAll();
  const byRef=Object.fromEntries(components.map(c=>[c.getState_Designator(),c]));
  const moved=[];
  for(const p of design.parts.filter(p=>!p.pcb_only&&!p.ref.startsWith('TP'))){
    const c=byRef[p.ref];if(!c)throw new Error('PCB component missing '+p.ref);
    if(!p.placement_mm)throw new Error('Placement missing '+p.ref);
    await eda.pcb_PrimitiveComponent.modify(c,{x:mm(p.placement_mm[0]),y:mm(p.placement_mm[1]),rotation:p.pcb_rotation||0,
      layer:1,primitiveLock:true,addIntoBom:p.assembly!=='pad-only'});
    moved.push(p.ref);
  }
  const [polylines,nativePads,nativeRegions,nativeStrings,sourceRecords]=await Promise.all([
    eda.pcb_PrimitivePolyline.getAll(),eda.pcb_PrimitivePad.getAll(),
    eda.pcb_PrimitiveRegion.getAll(),eda.pcb_PrimitiveString.getAll(),boardRecords()
  ]);
  // A persisted state file is only a hint: reopened/imported projects may have new IDs.
  const outlineCandidates=polylines.filter(p=>p.getState_Layer()===11);
  let outline=outlineCandidates.find(p=>idOf(p)===state.outline)||one(outlineCandidates,'board outline');
  const outlinePolygon=eda.pcb_MathPolygon.createPolygon(['R',0,mm(42),mm(80),mm(42),0,mm(1)]);
  outline=outline?await eda.pcb_PrimitivePolyline.modify(outline,{net:'',layer:11,polygon:outlinePolygon,lineWidth:mm(.05),primitiveLock:true}):
    await eda.pcb_PrimitivePolyline.create('',11,outlinePolygon,mm(.05),true);
  if(!outline)throw new Error('Outline update failed');state.outline=idOf(outline);
  const mountCenters=[[3.5,3.5],[76.5,3.5],[3.5,38.5],[76.5,38.5]];
  state.holes=[];state.regions=[];state.mountRegions={};
  for(const [i,[x,y]]of mountCenters.entries()){
    const number='H'+(i+1);
    let hole=one(nativePads.filter(p=>p.getState_PadNumber()===number),'mounting hole '+number);
    const properties={layer:12,padNumber:number,x:mm(x),y:mm(y),rotation:0,pad:['ELLIPSE',mm(2.2),mm(2.2)],
      net:'',hole:['ROUND',mm(2.2)],holeOffsetX:0,holeOffsetY:0,holeRotation:0,metallization:false,primitiveLock:true};
    hole=hole?await eda.pcb_PrimitivePad.modify(hole,properties):
      await eda.pcb_PrimitivePad.create(12,number,mm(x),mm(y),0,properties.pad,'',properties.hole,0,0,0,false,0,undefined,null,null,true);
    if(!hole)throw new Error('Hole update failed '+number);state.holes.push(idOf(hole));
    for(const layer of [1,2]){
      const key=(i+1)+':'+layer;
      const matches=nativeRegions.filter(p=>{
        if(p.getState_Layer()!==layer)return false;
        const d=sourceRecords.get('REGION:'+idOf(p)),circle=findPath(d?.path,'CIRCLE');
        return circle&&near(circle[1],mm(x))&&near(Math.abs(circle[2]),mm(y))&&near(circle[3],mm(3));
      });
      let region=one(matches,'mount keepout '+key);
      const polygon=eda.pcb_MathPolygon.createPolygon(['CIRCLE',mm(x),mm(y),mm(3)]);
      const name='M2_'+(i+1)+'_keepout';
      region=region?await eda.pcb_PrimitiveRegion.modify(region,{layer,complexPolygon:polygon,ruleType:[2,5,6,7],regionName:name,lineWidth:mm(.1),primitiveLock:true}):
        await eda.pcb_PrimitiveRegion.create(layer,polygon,[2,5,6,7],name,mm(.1),true);
      if(!region)throw new Error('Keepout update failed '+key);
      state.mountRegions[key]=idOf(region);state.regions.push(idOf(region));
    }
  }
  for(const p of design.parts.filter(p=>p.pcb_only||p.ref.startsWith('TP'))){
    const [x,y]=p.placement_mm;
    let pad=one(nativePads.filter(q=>q.getState_PadNumber()===p.ref),'test pad '+p.ref);
    pad=pad?await eda.pcb_PrimitivePad.modify(pad,{layer:2,padNumber:p.ref,x:mm(x),y:mm(y),rotation:0,pad:['ELLIPSE',mm(1),mm(1)],net:p.pins['1'],hole:null,primitiveLock:true}):
      await eda.pcb_PrimitivePad.create(2,p.ref,mm(x),mm(y),0,['ELLIPSE',mm(1),mm(1)],p.pins['1'],null,0,0,0,false,1,undefined,null,null,true);
    if(!pad)throw new Error('Test pad update failed '+p.ref);state.testpads[p.ref]=idOf(pad);
  }
  const labels=[[8,3.5,'CALXUS Rev A',1.25],[8,6,'USB BUS POWER ONLY',.8],[11,39,'0 MINI  1 A  2 TI  3 UART',.8],[66,35.8,'MINI',.8],[67,26,'TI',.8],[67,18,'CASIO',.8],[65,10,'AUX 3V3',.8]];
  state.silk=[];
  for(const [x,y,text,size]of labels){
    let s=one(nativeStrings.filter(p=>{const d=sourceRecords.get('STRING:'+idOf(p));return d?.layerId===3&&d.text===text;}),'silkscreen '+text);
    if(!s)s=await eda.pcb_PrimitiveString.create(3,mm(x),mm(y),text,'default',mm(size),mm(.15),3,0,false,0,false,true);
    if(!s)throw new Error('Silkscreen create failed '+text);state.silk.push(idOf(s));
  }
  // Independently read back source geometry after native updates; stale IDs cannot pass.
  const verified=await boardRecords(),rect=findPath(verified.get('POLY:'+state.outline)?.path,'R');
  if(!rect||!near(rect[1],0)||!near(rect[2],mm(42))||!near(rect[3],mm(80))||!near(rect[4],mm(42)))throw new Error('Outline positive-Y readback failed');
  for(const [i,[x,y]]of mountCenters.entries())for(const layer of [1,2]){
    const circle=findPath(verified.get('REGION:'+state.mountRegions[(i+1)+':'+layer])?.path,'CIRCLE');
    if(!circle||!near(circle[1],mm(x))||!near(circle[2],mm(y))||!near(circle[3],mm(3)))throw new Error('Keepout positive-Y readback failed');
  }
  await write('pcb-build-state.json',state);
  const nativeSaved=await eda.pcb_Document.save();
  return {moved:moved.length,outline:state.outline,holes:state.holes.length,keepouts:state.regions.length,testpads:Object.keys(state.testpads).length,nativeSaved,positiveYGeometryVerified:true};
}
if(args.stage==='pads'){
  const components=await eda.pcb_PrimitiveComponent.getAll();
  const out=[];
  for(const c of components){
    const pads=await eda.pcb_PrimitiveComponent.getAllPinsByPrimitiveId(c.getState_PrimitiveId());
    out.push({ref:c.getState_Designator(),id:c.getState_PrimitiveId(),x:c.getState_X(),y:c.getState_Y(),rotation:c.getState_Rotation(),layer:c.getState_Layer(),
      pads:pads.map(p=>({id:p.getState_PrimitiveId(),number:p.getState_PadNumber(),net:p.getState_Net(),x:p.getState_X(),y:p.getState_Y(),layer:p.getState_Layer(),rotation:p.getState_Rotation()}))});
  }
  await write('pcb-components-pads.json',{units:'mil',components:out,testpads:state.testpads});
  return {units:'mil',components:out,testpads:state.testpads};
}
if(args.stage==='rules'){
  for(const base of ['USB_UP','USB_NATIVE','USB_A','USB_SIL','USB_UART']){
    if(state.pairs.includes(base))continue;
    const ok=await eda.pcb_Drc.createDifferentialPair(base,base+'_DP',base+'_DM');
    if(ok)state.pairs.push(base);
  }
  const config=await eda.pcb_Drc.getCurrentRuleConfiguration();
  const stackup=await eda.pcb_Layer.getStackup();
  await write('pcb-rules-current.json',config);
  await write('pcb-stackup-current.json',stackup);
  await write('pcb-build-state.json',state);
  return {config,stackup,pairs:state.pairs};
}
throw new Error('Unknown stage '+args.stage);
