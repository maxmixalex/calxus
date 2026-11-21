/* Native audited routing handoff. No geometry changes except explicit pour rebuild. */
const ROOT='D:/Works/Calc/Calxus/engineering/';
const PCB='2a0c39c6c6694f40',PROJECT='6f31bb473de1899361a57910c51c08e861ce117b8335b0b090c2886f654c0785';
const a=__CLI__.args||{},stage=a.stage||'manifest';
const active=await eda.dmt_SelectControl.getCurrentDocumentInfo();
if(active?.uuid!==PCB||active.parentProjectUuid!==PROJECT||active.documentType!==3)throw Error('Wrong active PCB');
const read=async f=>JSON.parse(await(await eda.sys_FileSystem.readFileFromFileSystem(ROOT+f)).text());
async function save(name,data){const s=typeof data==='string'?data:JSON.stringify(data,null,2);if(!await eda.sys_FileSystem.saveFileToFileSystem(ROOT+name,new Blob([s])))throw Error('Write failed '+name);if(await(await eda.sys_FileSystem.readFileFromFileSystem(ROOT+name)).text()!==s)throw Error('Readback failed '+name);return {name,bytes:s.length};}
const state=await read('complete-route-import-state.json'),plan=await read('partial_route_plan.json');
if(state.pending||state.next!==plan.tracks.length+plan.vias.length||state.savedThrough!==state.next)throw Error('Import is not complete and saved');
if(stage==='manifest'){
 const vias=await eda.pcb_PrimitiveVia.getAll(),map=new Map(vias.map(v=>[v.getState_PrimitiveId(),v]));
 const records=[];
 for(const x of state.primitives.filter(x=>x.kind==='via')){
  const v=map.get(x.id),p=plan.vias.find(v=>v.tag===x.tag);if(!v||!p)throw Error('Missing reviewed via '+x.tag);
  records.push({primitiveId:x.id,tag:x.tag,net:v.getState_Net(),x_mm:v.getState_X()*.0254,y_mm:v.getState_Y()*.0254,holeDiameter_mm:v.getState_HoleDiameter()*.0254,diameter_mm:v.getState_Diameter()*.0254,classification:'ordinary-through-via',VIPPO:false,source:p.sourceViaIndex===undefined?'reviewed-additional':'restored-candidate4',planSHA256:state.planSHA256,solderMaskExpansion_mil:v.getState_SolderMaskExpansion()});
 }
 if(records.length!==128)throw Error('Expected128 new/restored vias');
 const vippoIds=['17077d66f911113b','89573436f3d877d6','400bbe0a7d6d643b','42761d9427b0bc87'];
 const originalVIPPO=vippoIds.map(id=>{const v=map.get(id);if(!v)throw Error('Missing approved VIPPO '+id);return {primitiveId:id,net:v.getState_Net(),x_mm:v.getState_X()*.0254,y_mm:v.getState_Y()*.0254,holeDiameter_mm:v.getState_HoleDiameter()*.0254,diameter_mm:v.getState_Diameter()*.0254,classification:'approved-original-EP-VIPPO',VIPPO:true,footprintPad:['17077d66f911113b','89573436f3d877d6'].includes(id)?'U2.33':'U3.17'};});
 const report={schema:'calxus.native-route-via-manifest.v1',exportedAt:new Date().toISOString(),pcbId:PCB,projectUuid:PROJECT,planSHA256:state.planSHA256,actualTotalVias:vias.length,records,originalVIPPO,measurementNote:'Native mm coordinates; verify actual Gerber mask openings and Excellon. Tented getters are supporting evidence only.',planNoteCorrection:'TP6 center remains(28,23.5)mm; the manufacturing-margin revision moved its external via to(28,22.74)mm. The earlier review prose in immutable plan says22.8; via coordinates and adjustment notes are authoritative.'};
 return {file:await save('native-final-route-via-manifest.json',report),ordinary:records.length,originalVIPPO:originalVIPPO.length,totalVias:vias.length};
}
if(stage==='drc'){
 const rebuilt=await eda.pcb_PrimitivePour.rebuildAllCopperRegions();const nativeSaved=await eda.pcb_Document.save();if(nativeSaved!==true)throw Error('Native save failed after rebuild');
 let result,error;try{result=await eda.pcb_Drc.checkDetailed({includeGroups:true});}catch(e){error={message:String(e),code:e?.code};result=await eda.pcb_Drc.getDrcResult();}
 const report={schema:'calxus.native-final-route-drc.v1',checkedAt:new Date().toISOString(),planSHA256:state.planSHA256,rebuilt,nativeSaved,error,result};const f=await save('native-final-route-drc.json',report);await save('pcb-complete-route-after-drc.epcb2',await eda.sys_FileManager.getDocumentSource());
 return {file:f,error,state:result?.state,totalCount:result?.totalCount,failedItems:result?.failedItems,groups:result?.groups,violations:result?.violations?.slice(0,20),nativeSaved,rebuilt};
}
if(stage==='backup'){
 if(!await eda.pcb_Document.save())throw Error('Save failed');const raw=await eda.sys_FileManager.getDocumentSource();const rawFile=await save('pcb-complete-route-before-reload.epcb2',raw);
 const name='Calxus_r7_complete_route_before_reload.epro2',f=await eda.sys_FileManager.getProjectFileByProjectUuid(PROJECT,'Calxus_r7_complete_route_before_reload',undefined,'epro2');
 if(!f||f.size<=0)throw Error('Empty project backup');const expected=new Uint8Array(await f.arrayBuffer());if(expected[0]!==80||expected[1]!==75)throw Error('Project backup is not ZIP');
 if(!await eda.sys_FileSystem.saveFileToFileSystem(ROOT+name,f,undefined,true))throw Error('Backup save failed');const actual=new Uint8Array(await(await eda.sys_FileSystem.readFileFromFileSystem(ROOT+name)).arrayBuffer());if(actual.length!==expected.length||actual.some((v,i)=>v!==expected[i]))throw Error('Backup byte readback mismatch');
 const report={schema:'calxus.route-before-reload-backup.v1',savedAt:new Date().toISOString(),planSHA256:state.planSHA256,projectUuid:PROJECT,pcbId:PCB,archive:{name,bytes:f.size,readbackByteIdentical:true},rawFile,checkpoint:state.next};await save('route-before-reload-backup.json',report);return report;
}
if(stage==='reload'){
 const backup=await read('route-before-reload-backup.json');if(backup.checkpoint!==state.next||backup.planSHA256!==state.planSHA256)throw Error('Backup checkpoint differs');
 const f=await eda.sys_FileSystem.readFileFromFileSystem(ROOT+backup.archive.name);if(!f||f.size!==backup.archive.bytes)throw Error('Backup absent');
 if(!await eda.pcb_Document.save())throw Error('Last save before reload failed');if(!await eda.dmt_EditorControl.closeDocument(active.tabId))throw Error('Close failed');
 const tab=await eda.dmt_EditorControl.openDocument(PCB);await eda.dmt_EditorControl.activateDocument(tab);if(!await eda.dmt_EditorControl.waitForDocumentReady(tab))throw Error('Reload not ready');
 const now=await eda.dmt_SelectControl.getCurrentDocumentInfo();if(now.uuid!==PCB||now.parentProjectUuid!==PROJECT)throw Error('Reloaded wrong document');
 const components=await eda.pcb_PrimitiveComponent.getAll(),j2=components.find(c=>c.getState_Designator()==='J2');if(!j2)throw Error('J2 absent');const pins=await eda.pcb_PrimitiveComponent.getAllPinsByPrimitiveId(j2.getState_PrimitiveId());
 const pads=pins.map(p=>({id:p.getState_PrimitiveId(),number:p.getState_PadNumber(),net:p.getState_Net(),x:p.getState_X(),y:p.getState_Y(),pad:p.getState_Pad(),hole:p.getState_Hole(),holeRotation:p.getState_HoleRotation(),mask:p.getState_SolderMaskAndPasteMaskExpansion()}));
 const report={schema:'calxus.native-route-reload.v1',reloadedAt:new Date().toISOString(),active:now,componentCount:components.length,lineCount:(await eda.pcb_PrimitiveLine.getAll()).length,viaCount:(await eda.pcb_PrimitiveVia.getAll()).length,j2Id:j2.getState_PrimitiveId(),j2PadsGetter: pads,warning:'Getter hole dimensions were previously affected by unit conversion; final actual Excellon/STEP drill inspection is required.'};await save('native-route-reload.json',report);return report;
}
throw Error('Unknown stage '+stage);
