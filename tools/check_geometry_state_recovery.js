/* Offline behavioral check: no editor connection or canvas operations.
 * Covers stale cached IDs, negative-Y legacy geometry, one missing object per
 * category, and repeated runs without duplicate primitives.
 */
const fs=require('fs'),path=require('path'),assert=require('assert');
const root=path.resolve(__dirname,'..');
const design=JSON.parse(fs.readFileSync(path.join(root,'hardware/electrical/calxus_design_input.json')));
const mm=n=>n/.0254,clone=x=>JSON.parse(JSON.stringify(x));
const pcb='2a0c39c6c6694f40';let serial=0,creates=0;
const data=Object.fromEntries(['component','poly','pad','region','string','pour'].map(k=>[k,new Map()]));
class Primitive{
  constructor(kind,d,id){this.kind=kind;this.d=d;this.id=id||kind+'_'+(++serial);data[kind].set(this.id,this);}
  getState_PrimitiveId(){return this.id;}
  getState_Layer(){return this.d.layer;}
  getState_Designator(){return this.d.ref;}
  getState_PadNumber(){return this.d.padNumber;}
  getState_Net(){return this.d.net;}
}
function add(k,d){return new Primitive(k,clone(d));}
const centers=[[3.5,3.5],[76.5,3.5],[3.5,38.5],[76.5,38.5]];
const labels=['CALXUS Rev A','USB BUS POWER ONLY','0 MINI  1 A  2 TI  3 UART','MINI','TI','CASIO','AUX 3V3'];
for(const p of design.parts.filter(p=>!p.pcb_only&&!p.ref.startsWith('TP')))add('component',{ref:p.ref,layer:1});
add('poly',{layer:11,polygon:['R',0,0,mm(80),mm(42),0,mm(1)]});
for(const [i,[x,y]]of centers.entries()){
  add('pad',{layer:12,padNumber:'H'+(i+1),x:mm(x),y:mm(y)});
  for(const layer of [1,2])add('region',{layer,complexPolygon:['CIRCLE',mm(x),-mm(y),mm(3)]});
}
for(const p of design.parts.filter(p=>p.pcb_only||p.ref.startsWith('TP')))add('pad',{layer:2,padNumber:p.ref,x:0,y:0,net:p.pins['1']});
for(const text of labels)add('string',{layer:3,text});
for(const layer of [15,16])add('pour',{layer,net:'GND',pourName:'legacy_name',complexPolygon:['R',mm(.5),-mm(.5),mm(79),mm(41),0,mm(.5)]});
const state={testpads:Object.fromEntries(design.parts.filter(p=>p.ref.startsWith('TP')).map(p=>[p.ref,'gone_'+p.ref])),
  outline:'gone_outline',holes:['gone_hole'],regions:Array(8).fill('gone_region'),silk:['gone_silk'],pairs:[],planes:{15:'gone15',16:'gone16'}};
const files=new Map([['design-input.json',JSON.stringify(design)],['pcb-build-state.json',JSON.stringify(state)]]);
let rules={Physics:{Track:{copperThickness1oz:{form:{data:{'1':{}}}}},'Differential Pair':{differentialPair:{form:{strokeWidthTables:{data:{}},diffPairSpacingTables:{data:{}}}}},'Via Size':{viaSize:{form:{}}}},Spacing:{'Safe Spacing':{copperThickness1oz:{tables:{a:{content:Array.from({length:7},()=>Array(7).fill(0))}}}}}};
const netRules=[{name:'VBUS_IN'},{name:'VBUS_NATIVE'},{name:'VBUS_USBA'}];
function api(kind,create){return {getAll:async()=>[...data[kind].values()],
  modify:async(p,changes)=>{if(typeof p==='string')p=data[kind].get(p);assert(p);p.d={...p.d,...clone(changes)};return p;},
  create:async(...args)=>{creates++;return add(kind,create(...args));}};}
function source(){
  const rows=[JSON.stringify({type:'DOCHEAD'})+'||'+JSON.stringify({uuid:pcb,docType:'PCB'})+'|'];
  const push=(type,p,d)=>rows.push(JSON.stringify({type,id:p.id})+'||'+JSON.stringify(d)+'|');
  for(const p of data.poly.values())push('POLY',p,{layerId:p.d.layer,path:p.d.polygon});
  for(const p of data.region.values())push('REGION',p,{layerId:p.d.layer,path:[p.d.complexPolygon],name:'PROHIBIT'});
  for(const p of data.string.values())push('STRING',p,{layerId:p.d.layer,text:p.d.text});
  for(const p of data.pour.values())push('POUR',p,{layerId:p.d.layer,netName:p.d.net,path:[p.d.complexPolygon],name:p.d.pourName});
  return rows.join('\n')+'\n';
}
const eda={
  sys_FileSystem:{readFileFromFileSystem:async p=>{const t=files.get(path.basename(p));return t===undefined?undefined:{text:async()=>t};},
    saveFileToFileSystem:async(p,b)=>{files.set(path.basename(p),await b.text());return true;}},
  sys_FileManager:{getDocumentSource:async()=>source()},
  dmt_EditorControl:{openDocument:async()=> 'mocktab',activateDocument:async()=>true,waitForDocumentReady:async()=>true},
  pcb_MathPolygon:{createPolygon:clone},pcb_Document:{save:async()=>true},
  pcb_PrimitiveComponent:api('component'),
  pcb_PrimitivePolyline:api('poly',(net,layer,polygon,lineWidth,primitiveLock)=>({net,layer,polygon,lineWidth,primitiveLock})),
  pcb_PrimitivePad:api('pad',(layer,padNumber,x,y,rotation,pad,net,hole)=>({layer,padNumber,x,y,rotation,pad,net,hole})),
  pcb_PrimitiveRegion:api('region',(layer,complexPolygon,ruleType,regionName,lineWidth,primitiveLock)=>({layer,complexPolygon,ruleType,regionName,lineWidth,primitiveLock})),
  pcb_PrimitiveString:api('string',(layer,x,y,text)=>({layer,x,y,text})),
  pcb_PrimitivePour:api('pour',(net,layer,complexPolygon,pourFillMethod,preserveSilos,pourName)=>({net,layer,complexPolygon,pourFillMethod,preserveSilos,pourName})),
  pcb_Drc:{getCurrentRuleConfiguration:async()=>({config:clone(rules)}),overwriteCurrentRuleConfiguration:async c=>(rules=clone(c),true),
    getNetRules:async()=>clone(netRules),overwriteNetRules:async()=>true}
};
eda.pcb_PrimitivePour.rebuildAllCopperRegions=async()=>[...data.pour.keys()];
const AsyncFunction=Object.getPrototypeOf(async function(){}).constructor;
const layout=new AsyncFunction('eda','__CLI__',fs.readFileSync(path.join(root,'automation/lceda_pcb.js'),'utf8'));
const planes=new AsyncFunction('eda','__CLI__',fs.readFileSync(path.join(root,'automation/lceda_rules_planes.js'),'utf8'));
const counts=()=>Object.fromEntries(Object.entries(data).map(([k,v])=>[k,v.size]));
async function run(){const a=await layout(eda,{args:{stage:'layout'}}),b=await planes(eda,{args:{}});assert(a.positiveYGeometryVerified&&b.positiveYGeometryVerified);return {a,b};}
(async()=>{
  const initial=counts();await run();assert.deepStrictEqual(counts(),initial);assert.strictEqual(creates,0);
  const recovered=JSON.parse(files.get('pcb-build-state.json'));
  assert(data.poly.has(recovered.outline));assert(recovered.regions.every(id=>data.region.has(id)));
  for(const id of Object.values(recovered.testpads))assert(data.pad.has(id));
  for(const id of Object.values(recovered.planes))assert(data.pour.has(id));
  data.region.delete(data.region.keys().next().value);
  const tp=[...data.pad.values()].find(p=>p.d.padNumber.startsWith('TP'));data.pad.delete(tp.id);
  data.pour.delete(data.pour.keys().next().value);
  await run();assert.deepStrictEqual(counts(),initial);assert.strictEqual(creates,3);
  await run();assert.deepStrictEqual(counts(),initial);assert.strictEqual(creates,3);
  const report={scope:'Offline mock API behavior only; no native editor/canvas execution',pass:true,
    scenarios:['stale cached IDs + existing primitives reused','negative-Y outline/keepouts/planes corrected','one missing keepout/testpad/plane recreated','repeat run creates no duplicates'],
    final_counts:counts(),new_primitives_after_three_runs:creates,actual_native_run_performed:false};
  fs.writeFileSync(path.join(root,'validation/geometry-state-recovery-offline.json'),JSON.stringify(report,null,2)+'\n');
  console.log(JSON.stringify(report));
})().catch(e=>{console.error(e);process.exitCode=1;});
