/* Native JLCEDA autorouter controller for ordinary nets. USB routes stay locked.
 * args: {stage:'start',nets?:[...],layers?:[1,2],optimization?:0|1} or {stage:'status'}.
 * Temporary L4 no-routing regions protect the reviewed USB copper corridors.
 * They are removed only after copper commits; final geometry is checked again.
 * Poll the recorded job until completed: cancellation discards calculated copper.
 */
const ROOT='D:/Works/Calc/Calxus/engineering/';
const PCB='2a0c39c6c6694f40';
const args=__CLI__.args||{};
const tab=await eda.dmt_EditorControl.openDocument(PCB);
await eda.dmt_EditorControl.activateDocument(tab);
if(!await eda.dmt_EditorControl.waitForDocumentReady(tab))throw new Error('PCB not ready');
async function read(name,fallback){
  const f=await eda.sys_FileSystem.readFileFromFileSystem(ROOT+name);
  if(!f)return fallback;
  const d=JSON.parse(await f.text());
  return d?.success===false&&d.code?fallback:d;
}
async function save(name,data){
  if(!await eda.sys_FileSystem.saveFileToFileSystem(ROOT+name,new Blob([typeof data==='string'?data:JSON.stringify(data,null,2)])))throw new Error('Cannot save '+name);
}
const state=await read('autoroute-state.json',{jobs:[]});
async function clearCorridors(){
  if(state.tempRegions?.length){
    if(!await eda.pcb_PrimitiveRegion.delete(state.tempRegions))throw new Error('Cannot remove temporary routing corridors');
    state.tempRegions=[];await save('autoroute-state.json',state);
  }
}
if(args.stage==='clearCorridors'){
  await clearCorridors();await eda.pcb_Document.save();return {temporaryCorridorsRemoved:true};
}
if(args.stage==='start'){
  if(state.current){
    const old=await eda.pcb_Document.getAutoJobStatus(state.current);
    if(old&&!['completed','failed','cancelled','canceled'].includes(old.state))throw new Error('Existing autorouter job is still active: '+state.current);
  }
  const plan=await read('usb_route_plan.json');
  const usb=await read('usb-route-state.json');
  if(!plan||!usb||usb.pending||usb.next!==plan.tracks.length+plan.vias.length)throw new Error('Finish reviewed USB copper before ordinary routing');
  const groundPlan=await read('ground_stitch_plan.json');
  const ground=await read('ground-route-state.json');
  if(!groundPlan||!ground||ground.pending||ground.next!==groundPlan.tracks.length+groundPlan.vias.length)throw new Error('Finish local ground returns before ordinary routing');
  const ignore=[...new Set(plan.tracks.map(x=>x.net))];
  const optimization=args.optimization===undefined?1:Number(args.optimization);
  if(![0,1].includes(optimization))throw new Error('Unsupported native routing optimization');
  const props={cornerStyle:0,existingPrimitiveMode:'keep',optimization,layers:args.layers||[1,2],ignoreNets:ignore};
  if(args.nets)props.RoutingNets=args.nets;
  const backup='pcb-before-autoroute-'+Date.now()+'.epro2';
  await save(backup,await eda.sys_FileManager.getDocumentSource());
  if(args.reserveUsbCorridors!==false&&!state.tempRegions?.length){
    const corridors=await read('usb_copper_corridors.json');
    if(corridors?.units!=='mil'||corridors.layer!==2||corridors.preexisting_conflicts?.length)throw new Error('Invalid USB corridor plan');
    state.tempRegions=[];
    for(const [i,area]of corridors.polygons.entries()){
      if(area.holes?.length)throw new Error('Unexpected corridor polygon holes');
      const p=area.exterior;
      const polygon=eda.pcb_MathPolygon.createPolygon([...p[0],'L',...p.slice(1).flat()]);
      if(!polygon)throw new Error('Invalid corridor polygon '+i);
      const region=await eda.pcb_PrimitiveRegion.create(2,polygon,[5],'TEMP_USB_ROUTE_RESERVATION_'+i,.1/.0254,true);
      if(!region)throw new Error('Cannot reserve USB corridor '+i);
      state.tempRegions.push(region.getState_PrimitiveId());await save('autoroute-state.json',state);
    }
  }
  await eda.pcb_Document.save();
  const handle=await eda.pcb_Document.startAutoRouting(props);
  if(!handle?.jobId)throw new Error('Missing native autorouter jobId: '+JSON.stringify(handle));
  state.current=handle.jobId;
  state.jobs.push({handle,props,backup,startedAt:new Date().toISOString()});
  await save('autoroute-state.json',state);
  return {handle,props,backup};
}
if(args.stage==='status'){
  if(!state.current)throw new Error('No recorded autorouter job');
  const status=await eda.pcb_Document.getAutoJobStatus(state.current);
  await save('autoroute-latest-status.json',status);
  if(status?.state==='completed'){
    await clearCorridors();
    await eda.pcb_PrimitivePour.rebuildAllCopperRegions();
    const nativeSaved=await eda.pcb_Document.save();
    const source=await eda.sys_FileManager.getDocumentSource();
    await save('pcb-after-autoroute-live.epro2',source);
    const readback=await eda.sys_FileSystem.readFileFromFileSystem(ROOT+'pcb-after-autoroute-live.epro2');
    if(await readback.text()!==source)throw new Error('Post-route source preservation mismatch');
    status.nativeSaved=nativeSaved;
    status.sourceBytes=source.length;
    state.jobs[state.jobs.length-1].completedStatus=status;
    await save('autoroute-state.json',state);
  }
  return status;
}
throw new Error('Unknown stage '+args.stage);
