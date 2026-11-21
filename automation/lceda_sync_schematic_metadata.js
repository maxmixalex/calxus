/* Targeted SCH instance metadata synchronization. No PCB/library/importChanges.
 * Requires page 01 already active in a previous invocation. args.stage=read|apply.
 * Effective source records are guarded apart from three authorized attribute values.
 */
const arg=__CLI__.args||{},stage=arg.stage||'read';
const page='0b9f8a9f53fb8264',project='6f31bb473de1899361a57910c51c08e861ce117b8335b0b090c2886f654c0785';
const changes=[
 {ref:'J2',id:'1488a7a605462dd5',key:'Calxus Function',old:'Selected downstream USB-A; rear separate shield pins 5/6 grounded; C456017 right-angle body10mm,height6.3mm.',next:'Selected downstream USB-A; C456017 rear shields5/6 grounded; right-angle10mm body6.3mm high.'},
 {ref:'J2',id:'1488a7a605462dd5',key:'3D Model Transform',old:null,inheritedOld:'562.991,393.7,0,0,0,0,-0.001,-157.48,-98.425',next:'562.991,393.7,0,0,0,0,-0.001,-157.48,-94.487992126'},
 {ref:'SW1',id:'33fbceeca2d73086',key:'3D Model Transform',old:null,inheritedOld:'590.55,218.5035,0,0,0,0,0,-38.031,-118.11',next:'590.55,218.5035,0,0,0,0,0,-38.031,-98.42496063'}
];
const current=await eda.dmt_SelectControl.getCurrentDocumentInfo();
if(current.uuid!==page||current.parentProjectUuid!==project||current.documentType!==1)throw new Error('Expected active USB schematic page');
function records(source){let doc='';const map=new Map();for(const line of source.split('\n')){if(!line.trim())continue;const i=line.indexOf('||');if(i<0)throw new Error('Unknown native source');const h=JSON.parse(line.slice(0,i)),raw=line.slice(i+2).replace(/\|\s*$/,'');const d=raw?JSON.parse(raw):null;if(h.type==='DOCHEAD')doc=d?.uuid||'';if(h.id){const k=doc+'|'+h.type+'|'+h.id;if(d===null)map.delete(k);else map.set(k,{h,d,doc});}}return map;}
function stable(x){if(Array.isArray(x))return x.map(stable);if(x&&typeof x==='object')return Object.fromEntries(Object.keys(x).sort().map(k=>[k,stable(x[k])]));return x;}
function protectedRecords(source){const out={};for(const [k,v] of records(source)){const c=JSON.parse(JSON.stringify(v));delete c.h.ticket;delete c.h.firstTicket;if(c.doc===page&&c.h.type==='ATTR'&&changes.some(x=>c.d.parentId===x.id&&c.d.key===x.key))continue;if(c.doc===page&&c.h.type==='COMPONENT')for(const ch of changes)if(c.h.id===ch.id&&c.d.attrs)delete c.d.attrs[ch.key];out[k]=c;}return stable(out);}
function diff(a,b){const keys=new Set([...Object.keys(a),...Object.keys(b)]);return [...keys].filter(k=>JSON.stringify(a[k])!==JSON.stringify(b[k]));}
async function saveText(path,txt){if(!await eda.sys_FileSystem.saveFileToFileSystem(path,new Blob([txt]),undefined,true))throw new Error('Backup failed '+path);const f=await eda.sys_FileSystem.readFileFromFileSystem(path);if(!f||await f.text()!==txt)throw new Error('Backup readback mismatch '+path);}
const root='D:/Works/Calc/Calxus/engineering/';
const preserved=arg.resume?await eda.sys_FileSystem.readFileFromFileSystem(root+'sch-before-metadata-sync.epru'):null;
const before=preserved?await preserved.text():await eda.sys_FileManager.getDocumentSource(),beforeProtected=protectedRecords(before),report={stage,checkedAt:new Date().toISOString(),current,changes,steps:[],protectedSourceUnchanged:false};
for(const ch of changes){const c=await eda.sch_PrimitiveComponent.get(ch.id);if(c.getState_Designator()!==ch.ref)throw new Error('Wrong ref');const v=c.getState_OtherProperty()?.[ch.key]??null;if(![ch.old,ch.inheritedOld,ch.next].includes(v))throw new Error('Unexpected old attribute '+ch.ref+' '+ch.key+' '+v);ch.actualApiBefore=v;}
if(stage==='read')return report;
if(stage!=='apply')throw new Error('Unsupported stage');
if(!arg.resume)await saveText(root+'sch-before-metadata-sync.epru',before);
for(const id of [...new Set(changes.map(x=>x.id))]){
 const c=await eda.sch_PrimitiveComponent.get(id),other={...c.getState_OtherProperty()};for(const ch of changes.filter(x=>x.id===id))other[ch.key]=ch.next;
 await eda.sch_PrimitiveComponent.modify(id,{otherProperty:other});
 const src=await eda.sys_FileManager.getDocumentSource(),after=protectedRecords(src),bad=diff(beforeProtected,after);
 const fresh=await eda.sch_PrimitiveComponent.get(id);
 const rawRecords=[...records(src).values()].filter(x=>x.doc===page&&x.h.type==='ATTR'&&x.d.parentId===id);
 const step={id,ref:fresh.getState_Designator(),protectedDiff:bad,values:changes.filter(x=>x.id===id).map(x=>({key:x.key,actual:rawRecords.find(r=>r.d.key===x.key)?.d.value,apiActual:fresh.getState_OtherProperty()?.[x.key]??null,expected:x.next,verification:'actual native ATTR value; SCH property getter omits reserved 3D attributes'}))};
 report.steps.push(step);
 if(bad.length||step.values.some(x=>x.actual!==x.expected)){await saveText(root+'sch-metadata-sync-unexpected.epru',src);await saveText(root+'sch-metadata-sync-report.json',JSON.stringify(report,null,2));throw new Error('Unexpected native mutation; see saved report, do not retry blindly');}
 step.saved=await eda.sch_Document.save();if(step.saved!==true)throw new Error('Native schematic save returned false after metadata change');
}
const after=await eda.sys_FileManager.getDocumentSource();await saveText(root+'sch-after-metadata-sync.epru',after);report.protectedSourceUnchanged=diff(beforeProtected,protectedRecords(after)).length===0;report.saved=true;
await saveText(root+'sch-metadata-sync-report.json',JSON.stringify(report,null,2));return report;
