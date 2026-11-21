/* Apply reviewed USB differential copper to the native Calxus PCB.
 * args: {stage:'apply',limit:25} or {stage:'export'}.
 * For reviewed GND stitching, pass planFile:'ground_stitch_plan.json',
 * stateFile:'ground-route-state.json', backupFile:'pcb-before-ground-routes.epro2',
 * and exportFile:'ground-routes-native.json'.
 * The plan and progress live under engineering/ on the user's machine.
 * Existing routed copper is preserved; all added USB copper is locked.
 */
const ROOT='D:/Works/Calc/Calxus/engineering/';
const PCB='2a0c39c6c6694f40';
const args=__CLI__.args||{};
const stateFile=args.stateFile||'usb-route-state.json';
const started=Date.now();
async function read(name,fallback){
  const file=await eda.sys_FileSystem.readFileFromFileSystem(ROOT+name);
  if(!file){if(fallback!==undefined)return fallback;throw new Error('Missing '+name);}
  const data=JSON.parse(await file.text());
  if(data?.success===false&&data.code){if(fallback!==undefined)return fallback;throw new Error(data.message);}
  return data;
}
async function save(name,data){
  const body=typeof data==='string'?data:JSON.stringify(data,null,2);
  if(!await eda.sys_FileSystem.saveFileToFileSystem(ROOT+name,new Blob([body])))throw new Error('Cannot save '+name);
}
function fingerprint(text){let h=2166136261;for(let i=0;i<text.length;i++)h=Math.imul(h^text.charCodeAt(i),16777619);return text.length+':'+(h>>>0).toString(16);}
const tab=await eda.dmt_EditorControl.openDocument(PCB);
await eda.dmt_EditorControl.activateDocument(tab);
if(!await eda.dmt_EditorControl.waitForDocumentReady(tab))throw new Error('PCB not ready');
const plan=await read(args.planFile||'usb_route_plan.json');
if(plan.units!=='mil')throw new Error('Unexpected route units');
if(plan.clearance_violations?.length||plan.warnings?.length||plan.geometry_violations?.length||plan.unresolved?.length)throw new Error('Plan has unresolved geometry findings');
const state=await read(stateFile,{next:0,primitives:[]});
const hash=fingerprint(JSON.stringify(plan));
if(state.planId&&state.planId!==hash)throw new Error('Changed route plan: inspect/remove previous copper before applying');
state.planId=hash;
if(state.pending)throw new Error('Uncertain prior mutation: inspect '+JSON.stringify(state.pending)+' before retrying');

if(args.stage==='apply'){
  if(!state.backup){
    state.backup=args.backupFile||'pcb-before-usb-routes.epro2';
    await save(state.backup,await eda.sys_FileManager.getDocumentSource());
    const rules=await eda.pcb_Drc.getCurrentRuleConfiguration();
    // JLC mechanical through vias: USB 0.20/0.50 mm; ordinary routing 0.30/0.60 mm.
    const form=rules.config.Physics['Via Size'].viaSize.form;
    form.viaInnerdiameterMin=.20;form.viaOuterdiameterMin=.50;
    form.viaInnerdiameterDefault=.30;form.viaOuterdiameterDefault=.60;
    await eda.pcb_Drc.overwriteCurrentRuleConfiguration(rules.config);
    await save(stateFile,state);
  }
  const items=[...plan.vias.map(v=>({kind:'via',...v})),...plan.tracks.map(t=>({kind:'line',...t}))];
  let applied=0;
  const limit=Math.min(40,Math.max(1,Number(args.limit)||25));
  while(state.next<items.length&&applied<limit&&Date.now()-started<42000){
    const item=items[state.next];
    state.pending={index:state.next,kind:item.kind,net:item.net,tag:item.tag};
    await save(stateFile,state);
    let p;
    if(item.kind==='via')p=await eda.pcb_PrimitiveVia.create(item.net,item.x,item.y,item.holeDiameter,item.diameter,0,null,null,true);
    else p=await eda.pcb_PrimitiveLine.create(item.net,item.layer,item.x1,item.y1,item.x2,item.y2,item.width,true);
    if(!p)throw new Error('Native creation failed at '+state.next);
    state.primitives.push({index:state.next,kind:item.kind,net:item.net,tag:item.tag,process_group:item.process_group,id:p.getState_PrimitiveId()});
    state.next++;applied++;delete state.pending;
    await save(stateFile,state);
  }
  const nativeSaved=await eda.pcb_Document.save();
  const source=await eda.sys_FileManager.getDocumentSource();
  const sourceFile=stateFile.replace(/\.json$/,'-live.epro2');
  await save(sourceFile,source);
  const verified=await eda.sys_FileSystem.readFileFromFileSystem(ROOT+sourceFile);
  if(await verified.text()!==source)throw new Error('Source backup readback mismatch');
  return {applied,next:state.next,total:items.length,done:state.next===items.length,nativeSaved,sourceFile,sourceBytes:source.length,elapsedMs:Date.now()-started};
}
if(args.stage==='export'){
  const nets=new Set(plan.tracks.map(t=>t.net));
  const lines=(await eda.pcb_PrimitiveLine.getAll()).filter(p=>nets.has(p.getState_Net())).map(p=>({id:p.getState_PrimitiveId(),net:p.getState_Net(),layer:p.getState_Layer(),x1:p.getState_StartX(),y1:p.getState_StartY(),x2:p.getState_EndX(),y2:p.getState_EndY(),width:p.getState_LineWidth()}));
  const vias=(await eda.pcb_PrimitiveVia.getAll()).filter(p=>nets.has(p.getState_Net())||state.primitives.some(s=>s.kind==='via'&&s.id===p.getState_PrimitiveId())).map(p=>({id:p.getState_PrimitiveId(),net:p.getState_Net(),x:p.getState_X(),y:p.getState_Y(),diameter:p.getState_Diameter(),holeDiameter:p.getState_HoleDiameter()}));
  const output={units:'mil',planId:hash,lines,vias};
  await save(args.exportFile||'usb-routes-native.json',output);
  return output;
}
throw new Error('Unknown stage '+args.stage);
