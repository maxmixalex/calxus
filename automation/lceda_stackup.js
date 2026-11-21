/* Populate physical stack order as well as enabling four electrical copper layers.
 * JLC04161H-7628, nominal 1.6 mm. The finished trace impedance result is recorded
 * separately because the fabricator's etch/plating model is not the CAD solid.
 */
const root='D:/Works/Calc/Calxus/engineering/';
const pcb='2a0c39c6c6694f40';
const tab=await eda.dmt_EditorControl.openDocument(pcb);
await eda.dmt_EditorControl.activateDocument(tab);
if(!await eda.dmt_EditorControl.waitForDocumentReady(tab))throw new Error('PCB not ready');
await eda.pcb_Layer.setTheNumberOfCopperLayers(4);
const before=await eda.pcb_Layer.getStackup();
const source=await eda.sys_FileManager.getDocumentSource();
await eda.sys_FileSystem.saveFileToFileSystem(root+'pcb-before-stackup.epcb2',new Blob([source]));
const records=[];
let inBoard=false;
for(const row of source.split('\n')){
  if(!row.trim())continue;
  const split=row.indexOf('||');if(split<0)throw new Error('Unknown source record');
  const h=JSON.parse(row.slice(0,split));
  const d=JSON.parse(row.slice(split+2).replace(/\|$/,''));
  if(h.type==='DOCHEAD')inBoard=d.uuid===pcb;
  records.push({h,d,inBoard});
}
const board=records.filter(r=>r.inBoard);
const key=r=>{try{return JSON.parse(r.h.id)[1];}catch{return undefined;}};
const top=board.find(r=>r.h.type==='LAYER_PHYS'&&key(r)===1);
const topBefore=before.layers.find(l=>l.layerId===1);
if(!top||!topBefore||before.unit!=='mil')throw new Error('Cannot establish physical units');
const sourcePerMil=top.d.thickness/topBefore.thickness;
const thick=mm=>mm/0.0254*sourcePerMil;
const wanted={
  1:{thickness:thick(.035),material:'Copper 1oz',zIndex:1000},
  361:{thickness:thick(.2104),material:'7628 prepreg',permittivity:4.4,lossTangent:.02,zIndex:1001},
  15:{thickness:thick(.0152),material:'Copper 0.5oz',permittivity:null,lossTangent:null,zIndex:2000},
  362:{thickness:thick(1.065),material:'FR-4 core',permittivity:4.6,lossTangent:.02,zIndex:2001},
  16:{thickness:thick(.0152),material:'Copper 0.5oz',permittivity:null,lossTangent:null,zIndex:3000},
  363:{thickness:thick(.2104),material:'7628 prepreg',permittivity:4.4,lossTangent:.02,zIndex:3001},
  2:{thickness:thick(.035),material:'Copper 1oz',zIndex:9000},
  5:{thickness:thick(.01),material:'Solder mask',permittivity:3.8,zIndex:3},
  6:{thickness:thick(.01),material:'Solder mask',permittivity:3.8,zIndex:10000},
};
let ticket=Math.max(...board.map(r=>r.h.ticket||0))+1;
for(const r of board){if(r.h.type==='LAYER_PHYS'&&wanted[key(r)]){Object.assign(r.d,wanted[key(r)]);r.h.ticket=ticket++;}}
const extra=[];
for(const [n,p]of Object.entries(wanted))if(!board.some(r=>r.h.type==='LAYER_PHYS'&&key(r)===Number(n))){extra.push({h:{type:'LAYER_PHYS',ticket:ticket++,id:JSON.stringify(['LAYER_PHYS',Number(n)])},d:{isKeepIsland:true,...p},inBoard:true});}
const substrate=board.find(r=>r.h.type==='LAYER'&&r.d.layerId===361);
if(!substrate)throw new Error('Missing substrate layer template');
for(const [id,name]of [[361,'PP7628 top'],[362,'FR4 core'],[363,'PP7628 bottom']]){
  const row=board.find(r=>r.h.type==='LAYER'&&r.d.layerId===id);
  if(row){row.d.layerName=name;row.d.use=true;row.h.ticket=ticket++;}
  else extra.push({h:{type:'LAYER',ticket:ticket++,id:JSON.stringify(['LAYER',id])},d:{...substrate.d,layerId:id,layerName:name,use:true},inBoard:true});
}
const last=records.reduce((a,r,i)=>r.inBoard?i:a,-1);
records.splice(last+1,0,...extra);
const updated=records.map(r=>JSON.stringify(r.h)+'||'+JSON.stringify(r.d)+'|').join('\n')+'\n';
const ok=await eda.sys_FileManager.setDocumentSource(updated);
if(!ok)throw new Error('Physical stackup update rejected');
await eda.dmt_EditorControl.waitForDocumentReady(tab);
await new Promise(resolve=>setTimeout(resolve,1200));
const after=await eda.pcb_Layer.getStackup();
const copper=after.layers.filter(l=>l.kind==='copper');
if(copper.map(l=>l.layerId).join(',')!=='1,15,16,2')throw new Error('Physical copper order did not persist: '+JSON.stringify(copper));
for(const id of [361,363]){const p=after.layers.find(l=>l.layerId===id);if(!p||Math.abs(p.thickness*.0254-.2104)>.001)throw new Error('Prepreg thickness mismatch');}
await eda.pcb_Document.save();
await eda.sys_FileSystem.saveFileToFileSystem(root+'pcb-stackup-verified.json',new Blob([JSON.stringify(after,null,2)],{type:'application/json'}));
return {sourcePerMil,stackup:after,thicknessMm:after.totalThickness*.0254};
