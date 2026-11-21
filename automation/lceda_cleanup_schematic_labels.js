/* Operate ONE already-open page. args: {stage:'preview'|'apply'|'verify',pageUuid,projectUuid}.
 * Activate the target in a separate invoke first. This script never opens a
 * different document. It changes only the guarded ATTR properties in the plan.
 * After apply, run verify in a separate invoke, then the full current 97/345/21 audit.
 */
const args=__CLI__.args||{},ROOT='D:/Works/Calc/Calxus/engineering/';
const stage=args.stage||'preview';
if(!['preview','apply','verify'].includes(stage)||!args.pageUuid||!args.projectUuid)throw new Error('Explicit stage/pageUuid/projectUuid required');
const info=await eda.dmt_SelectControl.getCurrentDocumentInfo();
if(info?.uuid!==args.pageUuid||info.parentProjectUuid!==args.projectUuid||info.documentType!==1)throw new Error('Wrong active schematic; activate the target in a separate invoke first');
await eda.dmt_EditorControl.activateDocument(info.tabId);
if(!await eda.dmt_EditorControl.waitForDocumentReady(info.tabId))throw new Error('Page not ready');
async function read(name){const f=await eda.sys_FileSystem.readFileFromFileSystem(ROOT+name);if(!f)throw new Error('Missing '+name);return JSON.parse(await f.text());}
async function save(name,value){const text=typeof value==='string'?value:JSON.stringify(value,null,2);if(!await eda.sys_FileSystem.saveFileToFileSystem(ROOT+name,new Blob([text]),undefined,true))throw new Error('Save failed '+name);}
const plan=await read(args.planFile||'schematic-label-cleanup.json'),page=plan.pages[args.pageUuid];
if(!page)throw new Error('Page absent from reviewed cleanup');
function parse(text){let doc;const rows=text.split('\n').map(raw=>{if(!raw.trim())return {raw,doc};const i=raw.indexOf('||');if(i<0)throw new Error('Unknown source record');const h=JSON.parse(raw.slice(0,i)),body=raw.slice(i+2).replace(/\|\s*$/,'');const d=body===''||body==='|'?null:JSON.parse(body);if(h.type==='DOCHEAD')doc=d.uuid;return {raw,h,d,doc};});const actual=new Map();for(const r of rows)if(r.doc===args.pageUuid&&r.h){const k=r.h.type+':'+r.h.id;if(r.d===null)actual.delete(k);else actual.set(k,r);}return {rows,actual};}
function stable(x){if(Array.isArray(x))return x.map(stable);if(x&&typeof x==='object')return Object.fromEntries(Object.keys(x).sort().map(k=>[k,stable(x[k])]));return x;}
function protectedData(actual){return [...actual.values()].filter(r=>['COMPONENT','WIRE','LINE','PIN'].includes(r.h.type)||(r.h.type==='ATTR'&&['NET','NO_CONNECT','Symbol','Device','Footprint','Designator'].includes(r.d.key))).map(r=>{const d=JSON.parse(JSON.stringify(r.d));if(r.h.type==='ATTR'&&r.d.key==='NET'){delete d.align;}return {key:r.h.type+':'+r.h.id,data:stable(d)};}).sort((a,b)=>a.key.localeCompare(b.key));}
function equalFields(actual,fields){return Object.entries(fields).every(([k,v])=>JSON.stringify(actual[k]??null)===JSON.stringify(v??null));}
const source=await eda.sys_FileManager.getDocumentSource(),parsed=parse(source);
const stateName=(args.statePrefix||'schematic-label-state-')+args.pageUuid+'.json';
if(stage==='verify'){
  const state=await read(stateName),failures=[];
  for(const action of page.actions){const r=parsed.actual.get('ATTR:'+action.id);if(!r||!equalFields(r.d,action.after))failures.push({id:action.id,reason:'Actual attribute differs from reviewed final properties'});}
  const current=protectedData(parsed.actual),old=new Map(state.protectedRecords.map(x=>[x.key,x.data]));
  for(const row of current){if(JSON.stringify(row.data)!==JSON.stringify(old.get(row.key)))failures.push({id:row.key,reason:'Protected geometry/electrical record changed'});old.delete(row.key);}
  for(const key of old.keys())failures.push({id:key,reason:'Protected record missing'});
  const report={stage,page:page.page_name,pass:failures.length===0,actions:page.actions.length,protectedRecords:current.length,failures};
  await save((args.verifyPrefix||'schematic-label-verify-')+args.pageUuid+'.json',report);return report;
}
const changes=[];
for(const action of page.actions){
  const row=parsed.actual.get('ATTR:'+action.id);if(!row)throw new Error('Missing actual ATTR '+action.id);
  if(equalFields(row.d,action.after))continue;
  if(!equalFields(row.d,action.before))throw new Error('Attribute precondition differs '+action.id+'; no source has changed');
  if(action.before.key==='NET'&&(Object.keys(action.changes).join()!=='align'||action.changes.align!=='RIGHT_BOTTOM'))throw new Error('Unapproved NET mutation');
  if(action.before.key!=='NET'&&(!['Page Size','Size'].includes(action.before.key)||action.changes.value!=='A2'))throw new Error('Unapproved title mutation');
  changes.push({action,row});
}
if(stage==='preview')return {stage,page:page.page_name,changes:changes.map(x=>x.action),netLabelsTotal:[...parsed.actual.values()].filter(x=>x.h.type==='ATTR'&&x.d.key==='NET').length};
const protectedRecords=protectedData(parsed.actual),backup='schematic-before-label-cleanup-'+args.pageUuid+'-'+Date.now()+'.epru';
await save(backup,source);await save(stateName,{pageUuid:args.pageUuid,backup,protectedRecords,actions:page.actions});
let ticket=Math.max(0,...parsed.rows.map(r=>Number(r.h?.ticket)||0))+1;
for(const {action,row}of changes){Object.assign(row.d,action.changes);row.h.ticket=ticket++;row.raw=JSON.stringify(row.h)+'||'+JSON.stringify(row.d)+'|';}
if(changes.length){if(!await eda.sys_FileManager.setDocumentSource(parsed.rows.map(r=>r.raw).join('\n')))throw new Error('Source update rejected');const saved=await eda.sch_Document.save();if(saved!==true)throw new Error('Native save returned false; source backup retained, do not close/reopen until persistence is resolved');}
return {stage,page:page.page_name,changed:changes.length,backup,requiresSeparateVerifyInvoke:true};
