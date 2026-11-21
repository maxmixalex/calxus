/* Apply the reviewed functional schematic plan in bounded native JLCEDA batches.
 * Run only through the root engineering task. This file does not run on load.
 * Files under ROOT: functional-schematic-plan.json, eda-bindings.json,
 * placement-state.json, and schematic-plan-state.json (created here).
 * args:
 *   {stage:'reset',page:'01_USB_Power'}        // one page, backup first
 *   {stage:'place',page?:...,offset:0,limit:8}
 *   {stage:'wire',page?:...,offset:0,limit:12} // offsets refer to filtered list
 *   {stage:'wire',page:...,resume:true,limit:30} // safely start at first unfinished polyline
 *   {stage:'annotate',page:...}               // block headings + usage note
 *   {stage:'labels',page:...}                 // optional raw NET anchor cleanup
 * Each return gives nextOffset/done. A 42 s soft budget stops between operations.
 * No footprint/device/BOM properties are changed. No component is re-created.
 */
const ROOT='D:/Works/Calc/Calxus/engineering/';
const arg=__CLI__.args||{};
const started=Date.now();
const budget=Math.min(42000,Math.max(5000,Number(arg.budgetMs)||42000));
const expired=()=>Date.now()-started>budget;
const STATE_NAME=arg.stateFile||'schematic-plan-state.json';
async function readJSON(name,fallback){
  const f=await eda.sys_FileSystem.readFileFromFileSystem(ROOT+name);
  if(!f){if(fallback!==undefined)return fallback;throw new Error('Missing '+name);}
  const value=JSON.parse(await f.text());
  if(value?.success===false&&value.code){if(fallback!==undefined)return fallback;throw new Error('Cannot read '+name+': '+value.message);}
  return value;
}
async function saveText(name,text){
  if(!await eda.sys_FileSystem.saveFileToFileSystem(ROOT+name,new Blob([text],{type:'text/plain'})))throw new Error('Cannot save '+name);
}
async function saveJSON(name,data){await saveText(name,JSON.stringify(data,null,2));}
function unwrap(r,context){if(!r?.ok)throw new Error(context+': '+JSON.stringify(r));return r.value;}
function fingerprint(text){let h=2166136261;for(let i=0;i<text.length;i++)h=Math.imul(h^text.charCodeAt(i),16777619);return text.length+':'+(h>>>0).toString(16);}
function parseSource(text){
  let page=null;
  return text.split('\n').map(raw=>{
    if(!raw.trim())return {raw,page};
    const cut=raw.indexOf('||');if(cut<0)throw new Error('Unknown native source record');
    const h=JSON.parse(raw.slice(0,cut));const d=JSON.parse(raw.slice(cut+2).replace(/\|\s*$/,''));
    if(h.type==='DOCHEAD')page=d.uuid;
    return {raw,h,d,page};
  });
}
function erasePageWires(text,pageUuid){
  const records=parseSource(text);
  if(!records.some(r=>r.h?.type==='DOCHEAD'&&r.d.uuid===pageUuid&&r.d.docType==='SCH_PAGE'))throw new Error('Target SCH_PAGE DOCHEAD absent: '+pageUuid);
  const ids=new Set(records.filter(r=>r.page===pageUuid&&r.h?.type==='WIRE').map(r=>r.h.id));
  if([...ids].some(id=>typeof id!=='string'))throw new Error('Unexpected WIRE header.id type');
  const removed={WIRE:0,LINE:0,ATTR:0};
  const keep=records.filter(r=>{
    if(r.page!==pageUuid||!r.h)return true;
    const drop=r.h.type==='WIRE'||(r.h.type==='LINE'&&ids.has(r.d.lineGroup))||(r.h.type==='ATTR'&&ids.has(r.d.parentId));
    if(drop)removed[r.h.type]++;
    return !drop;
  });
  return {text:keep.map(r=>r.raw).join('\n'),removed};
}
function onSegment(x,y,line){
  const sx=line.startX,sy=-line.startY,ex=line.endX,ey=-line.endY,e=1e-6;
  return Math.abs((x-sx)*(ey-sy)-(y-sy)*(ex-sx))<e&&x>=Math.min(sx,ex)-e&&x<=Math.max(sx,ex)+e&&y>=Math.min(sy,ey)-e&&y<=Math.max(sy,ey)+e;
}

const plan=await readJSON(arg.planFile||'functional-schematic-plan.json');
if(!plan.validation?.pass||!plan.validation.pin_net_equivalence_inferred_from_geometry_and_labels)throw new Error('Plan has not passed geometry/net validation');
const binding=await readJSON('eda-bindings.json');
const placement=await readJSON('placement-state.json');
const state=await readJSON(STATE_NAME,{schema:1,pages:{},placed:{},wireSegments:{},annotations:{}});
const planId=fingerprint(JSON.stringify(plan));
if(state.planId&&state.planId!==planId)throw new Error('Plan differs from saved progress. Use a new stateFile and reset each page; do not mix plans.');
state.planId=planId;
if(state.pending&&arg.stage!=='reset')throw new Error('Unresolved native mutation '+JSON.stringify(state.pending)+'. Inspect native result; reset and reapply that page if outcome is uncertain.');
if(state.pending&&arg.stage==='reset'&&arg.page!==state.pending.page)throw new Error('Resolve the pending page '+state.pending.page+' before resetting a different page');
const pages=[...new Set(Object.values(plan.components).map(c=>c.sheet))];
if(arg.page&&!pages.includes(arg.page))throw new Error('Unknown plan page '+arg.page);
const tabs={};
async function activate(page){
  if(!binding.pages[page])throw new Error('No bound page '+page);
  if(!tabs[page])tabs[page]=await eda.dmt_EditorControl.openDocument(binding.pages[page]);
  await eda.dmt_EditorControl.activateDocument(tabs[page]);
  if(!await eda.dmt_EditorControl.waitForDocumentReady(tabs[page]))throw new Error('Page not ready '+page);
  return tabs[page];
}
const source=page=>({projectId:binding.projectId,schematicName:binding.schematicName,pageName:page});
function requireReset(page){if(!state.pages[page]?.reset)throw new Error('Run reset for '+page+' before applying the plan');}
async function persist(){await saveJSON(STATE_NAME,state);}
async function savePage(page){
  await activate(page);
  if(await eda.sch_Document.save()!==true)throw new Error('Native schematic save failed for '+page+'; preserve live source and verify the project filesystem before closing or reloading.');
}
const results=[];

if(arg.stage==='reset'){
  const page=arg.page;if(!page)throw new Error('reset requires one page');
  await activate(page);
  const before=await eda.sys_FileManager.getDocumentSource();
  const backup='schematic-before-functional-'+page+'-'+Date.now()+'.epru';
  await saveText(backup,before);
  const cleaned=erasePageWires(before,binding.pages[page]);
  state.pending={stage:'reset',page,backup,when:new Date().toISOString()};await persist();
  await activate(page);
  if(!await eda.sys_FileManager.setDocumentSource(cleaned.text))throw new Error('Native source reset rejected');
  await activate(page);
  const after=await eda.sys_FileManager.getDocumentSource();
  if(parseSource(after).some(r=>r.page===binding.pages[page]&&r.h?.type==='WIRE'))throw new Error('WIRE remains after reset');
  // The stored geometry will be refreshed by place; component identity stays.
  for(const [ref,c]of Object.entries(plan.components))if(c.sheet===page){delete state.placed[ref];delete placement.wires?.[ref];}
  for(const [key,value]of Object.entries(state.wireSegments))if(value.page===page)delete state.wireSegments[key];
  // Annotation text is deliberately preserved by reset. Previously generated
  // headings remain recorded, so annotate is idempotent on a wire-only reset.
  state.pages[page]={reset:true,backup,removed:cleaned.removed,when:new Date().toISOString()};
  delete state.pending;await saveJSON('placement-state.json',placement);await persist();await savePage(page);
  return {stage:'reset',page,backup,removed:cleaned.removed,elapsedMs:Date.now()-started};
}

if(arg.stage==='place'){
  const list=Object.entries(plan.components).filter(([ref,c])=>!arg.page||c.sheet===arg.page);
  const offset=Math.max(0,Number(arg.offset)||0),limit=Math.min(12,Math.max(1,Number(arg.limit)||8));
  let i=offset;
  for(;i<Math.min(list.length,offset+limit);i++){
    if(expired())break;
    const [ref,c]=list[i];requireReset(c.sheet);
    if(state.placed[ref]){results.push({ref,skipped:true});continue;}
    const known=placement.components[ref]||binding.components?.[ref];
    if(!known?.primitiveId)throw new Error('No existing primitive for '+ref);
    await activate(c.sheet);
    const changed=unwrap(await eda.sch_SourcePrimitiveComponent.update({...source(c.sheet),primitiveId:known.primitiveId,x:c.x,y:c.y,rotation:0}),ref+' move');
    const item={...known,...changed};
    await activate(c.sheet);
    await eda.sch_PrimitiveComponent.modify(item.primitiveId,{mirror:!!c.mirror});
    const geometry=unwrap(await eda.sch_SourcePin.getGeometry({...source(c.sheet),primitiveId:item.primitiveId}),ref+' geometry');
    const expected=Object.values(plan.pin_endpoints).filter(p=>p.ref===ref);
    if(geometry.length!==expected.length)throw new Error(ref+' symbol pin count changed');
    for(const pin of geometry){
      const e=plan.pin_endpoints[ref+'.'+String(pin.pinNumber)];
      if(!e||Math.abs(e.x-pin.x)>.01||Math.abs(e.y-pin.y)>.01)throw new Error(ref+'.'+pin.pinNumber+' geometry disagrees with plan');
    }
    placement.components[ref]={...item,page:c.sheet,xy:[c.x,c.y],geometry};
    state.placed[ref]={page:c.sheet,primitiveId:item.primitiveId,when:new Date().toISOString()};
    await saveJSON('placement-state.json',placement);await persist();
    results.push({ref,x:c.x,y:c.y,pins:geometry.length});
  }
  return {stage:'place',count:results.length,total:list.length,nextOffset:i,done:i>=list.length,elapsedMs:Date.now()-started,results};
}

if(arg.stage==='wire'){
  const list=plan.wires.map((wire,index)=>({wire,index})).filter(x=>!arg.page||x.wire.sheet===arg.page);
  const unfinished=list.findIndex(({wire,index})=>wire.points.slice(1).some((_,segment)=>!state.wireSegments[index+':'+segment]));
  const offset=arg.resume?(unfinished<0?list.length:unfinished):Math.max(0,Number(arg.offset)||0);
  const limit=Math.min(30,Math.max(1,Number(arg.limit)||12));
  let i=offset;
  outer:for(;i<Math.min(list.length,offset+limit);i++){
    if(expired())break;
    const {wire:w,index}=list[i];requireReset(w.sheet);
    for(const [ref,c]of Object.entries(plan.components))if(c.sheet===w.sheet&&!state.placed[ref])throw new Error('Finish placement of '+w.sheet+' before wiring; missing '+ref);
    for(let seg=0;seg<w.points.length-1;seg++){
      const key=index+':'+seg;if(state.wireSegments[key])continue;
      if(expired())break outer;
      const a=w.points[seg],b=w.points[seg+1];
      if(a[0]!==b[0]&&a[1]!==b[1])throw new Error('Non-orthogonal planned segment '+key);
      state.pending={stage:'wire',page:w.sheet,wireIndex:index,segment:seg,net:w.net,when:new Date().toISOString()};await persist();
      await activate(w.sheet);
      // Two-point form is the already verified SourceWire API. Adjacent pieces
      // share exact endpoints; native EDA may merge their connected groups.
      const made=unwrap(await eda.sch_SourcePrimitiveWire.add({...source(w.sheet),line:[a[0],a[1],b[0],b[1]],net:w.net}),'wire '+key);
      state.wireSegments[key]={page:w.sheet,wireIndex:index,segment:seg,primitiveId:made?.primitiveId||null};
      delete state.pending;await persist();
    }
    results.push({wireIndex:index,page:w.sheet,net:w.net,segments:w.points.length-1});
  }
  return {stage:'wire',count:results.length,total:list.length,nextOffset:i,done:i>=list.length,elapsedMs:Date.now()-started,results};
}

if(arg.stage==='annotate'){
  const page=arg.page;if(!page)throw new Error('annotate requires one page');requireReset(page);
  const notes={
    '01_USB_Power':'SW1: 00=NATIVE, 01=USB-A, 10=SILVER, 11=UART. Disconnect upstream USB before changing mode.',
    '02_TI_SilverLink':'J9 fitted: EEPROM boot. J9 open before power: ROM recovery. J10 fitted enables EEPROM writes. Reprograms converter, not calculator.',
    '03_UART_Adapters':'J7: CASIO 1-3 + 2-4; AUX 3-5 + 4-6; no shunts=OFF. Select RX/TX as a pair. AUX pin 4 is NC.'};
  const entries=plan.blocks.filter(b=>b.sheet===page).map(b=>({key:b.id,text:b.title,x:b.heading.x,y:b.heading.y}));
  entries.push({key:'page-note',text:notes[page],x:100,y:315});
  for(const e of entries){
    if(expired())break;
    const key=page+':'+e.key;if(state.annotations[key])continue;
    state.pending={stage:'annotate',page,key,when:new Date().toISOString()};await persist();
    await activate(page);
    const made=unwrap(await eda.sch_SourcePrimitiveText.add({...source(page),text:e.text,x:e.x,y:e.y,rotation:0}),'heading '+key);
    state.annotations[key]={page,primitiveId:made?.primitiveId||null};delete state.pending;await persist();results.push(key);
  }
  await savePage(page);
  return {stage:'annotate',page,created:results,done:entries.every(e=>state.annotations[page+':'+e.key]),elapsedMs:Date.now()-started};
}

if(arg.stage==='labels'){
  const page=arg.page;if(!page)throw new Error('labels requires one page');requireReset(page);
  for(let i=0;i<plan.wires.length;i++)if(plan.wires[i].sheet===page){
    for(let j=0;j<plan.wires[i].points.length-1;j++)if(!state.wireSegments[i+':'+j])throw new Error('Finish all planned wires before arranging labels');
  }
  await activate(page);const before=await eda.sys_FileManager.getDocumentSource();
  const records=parseSource(before),uuid=binding.pages[page];
  const rows=records.filter(r=>r.page===uuid&&r.h);
  const wireIds=new Set(rows.filter(r=>r.h.type==='WIRE').map(r=>r.h.id));
  const lines=rows.filter(r=>r.h.type==='LINE'&&wireIds.has(r.d.lineGroup));
  const attrs=rows.filter(r=>r.h.type==='ATTR'&&r.d.key==='NET'&&wireIds.has(r.d.parentId));
  const selected=new Map();
  for(const lab of plan.net_labels.filter(l=>l.sheet===page)){
    // The editor can trim a redundant dead-end stub while merging connected
    // wires. Find the native owner through the actual island pin endpoints as
    // well as the preferred label anchor; never infer ownership from name alone.
    const endpoints=lab.island_pins.map(key=>plan.pin_endpoints[key]);
    const candidates=attrs.filter(a=>a.d.value===lab.net&&lines.some(l=>l.d.lineGroup===a.d.parentId&&(onSegment(lab.x,lab.y,l.d)||endpoints.some(p=>onSegment(p.x,p.y,l.d)))));
    if(!candidates.length)throw new Error('No native NET attribute touches planned island '+lab.net+' '+lab.pin+'; source has not been changed');
    const groups=new Map();for(const a of candidates)if(!groups.has(a.d.parentId))groups.set(a.d.parentId,a);
    for(const chosen of groups.values()){
      if(selected.has(chosen.h.id))continue;
      const own=lines.filter(l=>l.d.lineGroup===chosen.d.parentId);
      let anchor={...lab};
      if(!own.some(l=>onSegment(lab.x,lab.y,l.d))){
        const nearest=own.map(l=>{const x=Math.max(Math.min(l.d.startX,l.d.endX),Math.min(Math.max(l.d.startX,l.d.endX),lab.x));const y=Math.max(Math.min(-l.d.startY,-l.d.endY),Math.min(Math.max(-l.d.startY,-l.d.endY),lab.y));return {x,y,distance:Math.hypot(x-lab.x,y-lab.y)};}).sort((a,b)=>a.distance-b.distance)[0];
        if(!nearest)throw new Error('Native NET group has no line');anchor={...lab,x:nearest.x,y:nearest.y};
      }
      selected.set(chosen.h.id,anchor);
    }
  }
  const selectedGroups=new Set([...selected.keys()].map(id=>attrs.find(a=>a.h.id===id).d.parentId));
  const orphanGroups=[...new Set(attrs.map(a=>a.d.parentId))].filter(id=>!selectedGroups.has(id));
  if(orphanGroups.length)throw new Error('Native NET groups without any planned island pin: '+orphanGroups.join(',')+'; source has not been changed');
  const backup='schematic-before-label-layout-'+page+'-'+Date.now()+'.epru';await saveText(backup,before);
  let ticket=Math.max(0,...rows.map(r=>Number(r.h.ticket)||0))+1,changed=0;
  for(const a of attrs){
    const lab=selected.get(a.h.id);a.d.valueVisible=!!lab;
    if(lab){a.d.x=lab.x;a.d.y=-lab.y;a.d.rotation=lab.rotation||0;}
    a.h.ticket=ticket++;a.raw=JSON.stringify(a.h)+'||'+JSON.stringify(a.d)+'|';changed++;
  }
  state.pending={stage:'labels',page,backup,when:new Date().toISOString()};await persist();
  await activate(page);
  if(!await eda.sys_FileManager.setDocumentSource(records.map(r=>r.raw).join('\n')))throw new Error('NET label source update rejected');
  await activate(page);delete state.pending;state.pages[page].labels={backup,visible:selected.size,updated:changed};await persist();await savePage(page);
  return {stage:'labels',page,backup,visible:selected.size,updated:changed,elapsedMs:Date.now()-started};
}
throw new Error('Unknown stage '+arg.stage);
