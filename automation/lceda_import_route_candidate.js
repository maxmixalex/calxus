/* Apply the reviewed r7 complete routing plan from the saved iteration-4 candidate and audited additions by public primitives.
 * Invocation: args={stage:'preflight'|'apply'|'status',limit:40}; repeat apply.
 * Caller must first cancel the old job and verify its terminal state. This script
 * never cancels jobs, opens/activates documents, changes rules, or reads a live
 * route candidate. Keep the intended Calxus PCB active and invoke serially.
 * Files: engineering/partial_route_plan.json and complete-route-import-state.json.
 * A persisted pending item always blocks retry: inspect native geometry first.
 * Checkpoints ahead of the last native save require geometry readback on resume.
 */
const ROOT='D:/Works/Calc/Calxus/engineering/';
const PCB='2a0c39c6c6694f40';
const PLAN_FILE='partial_route_plan.json';
const STATE_FILE='complete-route-import-state.json';
const PLAN_SHA256='27e055ef8128dac9e3503b30208e29fd40e5a7d9eeab500c0546b907e6416423';
const PLAN_FINGERPRINT='499754:96d3ab4b';
const CANDIDATE_SHA256='b8e9ac424b1b66727e3a15dd2230a162bc49960c85d7159955c481b64614ab2c';
const args=__CLI__.args||{};
const stage=args.stage||'status';
const started=Date.now(),TOL=.11;
const PROJECT='6f31bb473de1899361a57910c51c08e861ce117b8335b0b090c2886f654c0785';
const active=await eda.dmt_SelectControl.getCurrentDocumentInfo();
if(active?.uuid!==(args.pcbId||PCB)||active.parentProjectUuid!==(args.projectUuid||PROJECT)||active.documentType!==3)throw Error('Wrong active reviewed PCB/project');
if(!['preflight','apply','status','save-checkpoint'].includes(stage))throw Error('Unknown stage '+stage);
async function readText(name,optional=false){
  const f=await eda.sys_FileSystem.readFileFromFileSystem(ROOT+name);
  if(!f){if(optional)return null;throw Error('Missing file '+name);}
  const text=await f.text();
  let envelope;try{envelope=JSON.parse(text);}catch{}
  if(envelope?.success===false&&envelope.code){if(optional)return null;throw Error(envelope.message||('Read error '+name));}
  return text;
}
async function readJSON(name,optional=false){const text=await readText(name,optional);return text===null?null:JSON.parse(text);}
async function save(name,data){
  const text=typeof data==='string'?data:JSON.stringify(data,null,2);
  if(!await eda.sys_FileSystem.saveFileToFileSystem(ROOT+name,new Blob([text])))throw Error('Cannot persist '+name);
  const f=await eda.sys_FileSystem.readFileFromFileSystem(ROOT+name);
  if(!f||await f.text()!==text)throw Error('Persistent readback mismatch '+name);
}
function fingerprint(s){let h=2166136261;for(let i=0;i<s.length;i++)h=Math.imul(h^s.charCodeAt(i),16777619);return s.length+':'+(h>>>0).toString(16);}

function sha256Ascii(s){
  const K=[0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2];
  const H=[0x6a09e667,0xbb67ae85,0x3c6ef372,0xa54ff53a,0x510e527f,0x9b05688c,0x1f83d9ab,0x5be0cd19];
  const b=Array.from(s,c=>c.charCodeAt(0));if(b.some(v=>v>127))throw Error('Reviewed plan must use ASCII JSON encoding');const bits=b.length*8;b.push(128);while(b.length%64!==56)b.push(0);for(let i=7;i>=0;i--)b.push(Math.floor(bits/2**(i*8))&255);
  const rr=(x,n)=>(x>>>n)|(x<<(32-n));
  for(let off=0;off<b.length;off+=64){const w=new Array(64);for(let i=0;i<16;i++)w[i]=(b[off+i*4]<<24)|(b[off+i*4+1]<<16)|(b[off+i*4+2]<<8)|b[off+i*4+3];for(let i=16;i<64;i++){const x=w[i-15],y=w[i-2];w[i]=(w[i-16]+(rr(x,7)^rr(x,18)^(x>>>3))+w[i-7]+(rr(y,17)^rr(y,19)^(y>>>10)))|0;}let[a,c,d,e,f,g,h,j]=H;for(let i=0;i<64;i++){const t1=(j+(rr(f,6)^rr(f,11)^rr(f,25))+((f&g)^(~f&h))+K[i]+w[i])|0;const t2=((rr(a,2)^rr(a,13)^rr(a,22))+((a&c)^(a&d)^(c&d)))|0;j=h;h=g;g=f;f=(e+t1)|0;e=d;d=c;c=a;a=(t1+t2)|0;}[a,c,d,e,f,g,h,j].forEach((v,i)=>H[i]=(H[i]+v)|0);}
  return H.map(v=>(v>>>0).toString(16).padStart(8,'0')).join('');
}

const planText=await readText(PLAN_FILE),plan=JSON.parse(planText);
if(fingerprint(planText)!==PLAN_FINGERPRINT||sha256Ascii(planText)!==PLAN_SHA256)throw Error('Plan bytes differ from reviewed fixed plan '+PLAN_SHA256);
if(plan.projectUuid!==PROJECT||plan.schema!=='calxus.partial-route-plan.v1'||plan.units!=='mil'||plan.pcbId!==PCB||plan.source.sha256!==CANDIDATE_SHA256||plan.source.iterationId!==4)throw Error('Wrong fixed candidate plan');
if(!plan.review.hard_geometry_passed||!plan.review.candidate_foreign_clearance_passed||!plan.review.usb_corridor_passed)throw Error('Reviewed geometry gates failed');
const items=[...plan.vias.map(v=>({kind:'via',...v})),...plan.tracks.map(t=>({kind:'line',...t}))];
const hs=new Set(plan.baseline.hsNets);
if(items.some(x=>hs.has(x.net)))throw Error('Recovery plan must not add ignored HS copper');
let state=await readJSON(STATE_FILE,true);
if(state&&state.planSHA256!==PLAN_SHA256)throw Error('State belongs to another plan');
state=state||{schema:'calxus.partial-route-import-state.v1',planSHA256:PLAN_SHA256,candidateSHA256:CANDIDATE_SHA256,pcbId:PCB,next:0,savedThrough:0,primitives:[],startedAt:new Date().toISOString()};
if(!Number.isInteger(state.next)||state.next<0||state.next>items.length||state.primitives.length!==state.next)throw Error('Invalid recovery checkpoint');
if(state.pending)throw Error('Uncertain previous mutation; inspect before retry: '+JSON.stringify(state.pending));

// Check both the fixed source job and the recorded controller job. No cancellation.
const controller=await readJSON('autoroute-state.json',true);
const jobIds=[...new Set([plan.source.jobId,controller?.current].filter(Boolean))];
const jobStates=[];
for(const jobId of jobIds){
  let s;try{s=await eda.pcb_Document.getAutoJobStatus(jobId);}catch(e){jobStates.push({jobId,state:'notAvailableInImportedProject',message:String(e).slice(0,160)});continue;}
  if(!s){jobStates.push({jobId,state:'notAvailableInImportedProject'});continue;}
  if(!['cancelled','canceled','failed','completed'].includes(s.state))throw Error('Routing job must be terminal before recovery: '+JSON.stringify(s));
  jobStates.push(s);
}
const lineData=p=>({id:p.getState_PrimitiveId(),net:p.getState_Net()||'',layer:p.getState_Layer(),x1:p.getState_StartX(),y1:p.getState_StartY(),x2:p.getState_EndX(),y2:p.getState_EndY(),width:p.getState_LineWidth(),locked:p.getState_PrimitiveLock()});
const viaData=p=>({id:p.getState_PrimitiveId(),net:p.getState_Net()||'',x:p.getState_X(),y:p.getState_Y(),diameter:p.getState_Diameter(),holeDiameter:p.getState_HoleDiameter(),solderMaskExpansion:p.getState_SolderMaskExpansion(),locked:p.getState_PrimitiveLock()});
async function readCopper(){const [ls,vs]=await Promise.all([eda.pcb_PrimitiveLine.getAll(),eda.pcb_PrimitiveVia.getAll()]);return {lines:ls.map(lineData),vias:vs.map(viaData)};}
const close=(a,b)=>Math.abs(a-b)<=TOL;
function sameLine(a,b){return a&&a.net===b.net&&a.layer===b.layer&&close(a.width,b.width)&&((close(a.x1,b.x1)&&close(a.y1,b.y1)&&close(a.x2,b.x2)&&close(a.y2,b.y2))||(close(a.x1,b.x2)&&close(a.y1,b.y2)&&close(a.x2,b.x1)&&close(a.y2,b.y1)));}
function sameVia(a,b){return a&&a.net===b.net&&['x','y','diameter','holeDiameter'].every(k=>close(a[k],b[k]));}
function covered(t,lines){
  const dx=t.x2-t.x1,dy=t.y2-t.y1,len=Math.hypot(dx,dy),spans=[];
  if(len<=TOL)return true;
  for(const a of lines){
    if(a.net!==t.net||a.layer!==t.layer||a.width<t.width-TOL)continue;
    const ax=a.x1-t.x1,ay=a.y1-t.y1,bx=a.x2-t.x1,by=a.y2-t.y1;
    if(Math.abs(ax*dy-ay*dx)/len>TOL||Math.abs(bx*dy-by*dx)/len>TOL)continue;
    const u=(ax*dx+ay*dy)/len,v=(bx*dx+by*dy)/len;
    const lo=Math.max(0,Math.min(u,v)),hi=Math.min(len,Math.max(u,v));
    if(hi>=lo-TOL)spans.push([lo,hi]);
  }
  spans.sort((a,b)=>a[0]-b[0]);let end=0;
  for(const [lo,hi]of spans){if(lo>end+TOL)return false;end=Math.max(end,hi);if(end>=len-TOL)return true;}
  return false;
}
async function verifyPlanes(){
  const ps=await eda.pcb_PrimitivePour.getAll();
  if(ps.length!==2)throw Error('Expected exactly two original GND planes, got '+ps.length);
  const pm=new Map(ps.map(p=>[p.getState_PrimitiveId(),p]));
  for(const b of plan.baseline.planes){
    const p=pm.get(b.id)||ps.find(q=>q.getState_Net()==='GND'&&q.getState_Layer()===b.layer&&JSON.stringify(q.getState_ComplexPolygon().getSource())===JSON.stringify(b.polygon));
    if(!p||p.getState_Net()!=='GND'||p.getState_Layer()!==b.layer||!p.getState_PrimitiveLock()||JSON.stringify(p.getState_ComplexPolygon().getSource())!==JSON.stringify(b.polygon))throw Error('Original GND plane differs '+b.id);
  }
}
function verifyBaseline(c,initial){
  if(initial&&(c.lines.length!==139||c.vias.length!==61))throw Error('Original copper has not been restored: '+c.lines.length+' lines / '+c.vias.length+' vias; expected139/61');
  const lm=new Map(c.lines.map(x=>[x.id,x])),vm=new Map(c.vias.map(x=>[x.id,x]));
  for(const b of plan.baseline.lines){
    const a=sameLine(lm.get(b.id),b)?lm.get(b.id):c.lines.find(q=>sameLine(q,b));
    if(initial||hs.has(b.net)){if(!sameLine(a,b)||!a.locked)throw Error('Original locked copper changed '+b.id);}
    else if(!covered(b,c.lines))throw Error('Original GND line coverage lost '+b.id);
  }
  for(const b of plan.baseline.vias){const a=sameVia(vm.get(b.id),b)?vm.get(b.id):c.vias.find(q=>sameVia(q,b));if(!sameVia(a,b)||!a.locked)throw Error('Original locked via changed '+b.id);}
  for(const net of hs){
    const expectedL=plan.baseline.lines.filter(x=>x.net===net).length,expectedV=plan.baseline.vias.filter(x=>x.net===net).length;
    if(c.lines.filter(x=>x.net===net).length!==expectedL||c.vias.filter(x=>x.net===net).length!==expectedV)throw Error('Unexpected original HS copper count '+net);
  }
}
// Native merge removed this 1.69mil dead-end. Exact geometric review shows
// it touches no pad and adds no connectivity; actual copper is a subset of plan.
// Keep the exception bound to one immutable-plan tag and both surviving branches.
function reviewedNativeTrim(t,lines){
  if(!['iteration4_trace429_segment1','iteration4_trace431_segment0'].includes(t.tag)||t.net!=='PWR_FAULT_N'||t.layer!==1)return false;
  const joint={x:744.5195979594172,y:253.94986286707407};
  const branch={net:t.net,layer:1,width:t.width,x1:768.3095851128242,y1:277.739850020481,x2:joint.x,y2:joint.y};
  const trunk={net:t.net,layer:1,width:t.width,x1:773.6195822454258,y1:253.93986287247407,x2:joint.x,y2:joint.y};
  if(!covered(branch,lines)||!covered(trunk,lines))return false;
  return Math.hypot(t.x2-joint.x,t.y2-joint.y)<t.width/2-.5;
}
// Native removed the 6mil duplicate part inside an existing9.53125mil SIL DM
// trace, retaining the6mil extension to the moved via. The last0.755118mil
// is contained by the wider round end cap:0.755118+3<9.53125/2.
function reviewedWideTraceCoverage(t,lines){
  if(t.tag!=='mask_margin_additional_12_via0_stub0'||t.net!=='USB_SIL_DM'||t.layer!==1)return false;
  const joint=684.0551181102362;
  if(!covered({...t,y2:joint},lines))return false;
  return lines.some(a=>a.net===t.net&&a.layer===1&&a.width>=9.53125-.0001&&close(a.x1,t.x1)&&close(a.x2,t.x1)&&Math.min(a.y1,a.y2)<=joint+TOL&&Math.max(a.y1,a.y2)>=691.9291338582677-TOL&&Math.max(0,t.y2-Math.max(a.y1,a.y2))+t.width/2<=a.width/2-TOL);
}
function verifyApplied(c){
  const vm=new Map(c.vias.map(x=>[x.id,x]));
  for(let i=0;i<state.next;i++){
    const x=items[i],record=state.primitives[i];
    if(record.index!==i)throw Error('Checkpoint index mismatch '+i);
    if(x.kind==='via'){const actual=vm.get(record.id);if(!sameVia(actual,x))throw Error('Checkpoint via missing or changed '+i);const mask=actual.solderMaskExpansion;if(!mask||!close(mask.topSolderMask,-x.diameter/2)||!close(mask.bottomSolderMask,-x.diameter/2))throw Error('New via tenting differs '+i);}
    else if(!covered(x,c.lines)&&!reviewedNativeTrim(x,c.lines)&&!reviewedWideTraceCoverage(x,c.lines))throw Error('Checkpoint line coverage missing '+i+'; do not blindly reapply');
  }
}
const before=await readCopper();
await verifyPlanes();verifyBaseline(before,state.next===0);verifyApplied(before);
if(stage==='save-checkpoint'){const nativeSaved=await eda.pcb_Document.save();if(nativeSaved!==true)throw Error('Resume save failed');state.savedThrough=state.next;state.lastSavedAt=new Date().toISOString();state.reviewedNativeTrimTags=['iteration4_trace429_segment1','iteration4_trace431_segment0'];await save(STATE_FILE,state);await save('pcb-complete-route-import-live.epcb2',await eda.sys_FileManager.getDocumentSource());return {next:state.next,savedThrough:state.savedThrough,total:items.length,nativeSaved,reviewedNativeTrimTags:state.reviewedNativeTrimTags};}
if(stage!=='apply')return {stage,planSHA256:PLAN_SHA256,candidateSHA256:CANDIDATE_SHA256,baselineVerified:true,planesVerified:2,jobStates,next:state.next,total:items.length,done:state.next===items.length,savedThrough:state.savedThrough,nativeCounts:{lines:before.lines.length,vias:before.vias.length},review:plan.review};
if(!state.backup){
  const source=await eda.sys_FileManager.getDocumentSource();
  state.backup='pcb-before-complete-route-import.epcb2';
  await save(state.backup,source);state.baselineVerifiedAt=new Date().toISOString();await save(STATE_FILE,state);
}
const limit=Math.min(40,Math.max(1,Math.floor(Number(args.limit)||40)));
let applied=0;
while(state.next<items.length&&applied<limit&&Date.now()-started<42000){
  const index=state.next,x=items[index];
  state.pending={index,kind:x.kind,net:x.net,tag:x.tag,when:new Date().toISOString()};
  await save(STATE_FILE,state); // Readback MUST succeed before native mutation.
  let p;
  if(x.kind==='via')p=await eda.pcb_PrimitiveVia.create(x.net,x.x,x.y,x.holeDiameter,x.diameter,0,null,{topSolderMask:-x.diameter/2,bottomSolderMask:-x.diameter/2},false);
  else p=await eda.pcb_PrimitiveLine.create(x.net,x.layer,x.x1,x.y1,x.x2,x.y2,x.width,false);
  if(!p)throw Error('Native creation failed at '+index);
  state.primitives.push({index,kind:x.kind,tag:x.tag,net:x.net,id:p.getState_PrimitiveId()});
  state.next++;applied++;delete state.pending;
  await save(STATE_FILE,state);
}
const after=await readCopper();
verifyBaseline(after,false);verifyApplied(after);await verifyPlanes();
const nativeSaved=await eda.pcb_Document.save();
if(nativeSaved===false)throw Error('Native document save failed; readback must be verified before resume');
state.savedThrough=state.next;state.lastSavedAt=new Date().toISOString();await save(STATE_FILE,state);
const source=await eda.sys_FileManager.getDocumentSource();
await save('pcb-complete-route-import-live.epcb2',source);
return {applied,next:state.next,total:items.length,done:state.next===items.length,savedThrough:state.savedThrough,nativeSaved,nativeCounts:{lines:after.lines.length,vias:after.vias.length},originalHSAndViasVerified:true,planesVerified:2,planSHA256:PLAN_SHA256,elapsedMs:Date.now()-started,nativeDRCStillRequired:true};
