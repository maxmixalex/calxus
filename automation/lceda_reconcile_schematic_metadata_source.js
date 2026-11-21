/* Exact source fallback for the three approved instance attributes.
 * SCH component.modify normalizes inherited fields and label alignment on SW1.
 * Restore original records and alter only the three approved values; no libraries,
 * PCB data, pins, wire groups, symbols, poses or visible labels may change.
 */
const root='D:/Works/Calc/Calxus/engineering/',page='0b9f8a9f53fb8264';
const info=await eda.dmt_SelectControl.getCurrentDocumentInfo();if(info.uuid!==page||info.documentType!==1)throw new Error('Wrong active page');
const f=await eda.sys_FileSystem.readFileFromFileSystem(root+'sch-before-metadata-sync.epru');if(!f)throw new Error('Missing protected original source');
const original=await f.text(),current=await eda.sys_FileManager.getDocumentSource();
function parse(s){let doc='';return s.split('\n').map(raw=>{if(!raw.trim())return{raw};const p=raw.indexOf('||'),h=JSON.parse(raw.slice(0,p)),v=raw.slice(p+2).replace(/\|\s*$/,''),d=v?JSON.parse(v):null;if(h.type==='DOCHEAD')doc=d?.uuid;return {raw,h,d,doc};});}
const changes=[{parentId:'1488a7a605462dd5',key:'Calxus Function',value:'Selected downstream USB-A; C456017 rear shields5/6 grounded; right-angle10mm body6.3mm high.'},{parentId:'1488a7a605462dd5',key:'3D Model Transform',value:'562.991,393.7,0,0,0,0,-0.001,-157.48,-94.487992126'},{parentId:'33fbceeca2d73086',key:'3D Model Transform',value:'590.55,218.5035,0,0,0,0,0,-38.031,-98.42496063'}];
const old=parse(original),now=parse(current),edits=[];
for(const ch of changes){let target=old.find(r=>r.doc===page&&r.h?.type==='ATTR'&&r.d?.parentId===ch.parentId&&r.d?.key===ch.key);if(target){edits.push({id:target.h.id,parentId:ch.parentId,key:ch.key,old:target.d.value,next:ch.value});target.d.value=ch.value;target.raw=JSON.stringify(target.h)+'||'+JSON.stringify(target.d)+'|';}else{const native=now.find(r=>r.doc===page&&r.h?.type==='ATTR'&&r.d?.parentId===ch.parentId&&r.d?.key===ch.key);if(!native||native.d.value!==ch.value)throw new Error('Missing observed native ATTR template');let last=-1;old.forEach((r,i)=>{if(r.doc===page)last=i;});if(last<0)throw new Error('Page scope missing');old.splice(last+1,0,native);edits.push({id:native.h.id,parentId:ch.parentId,key:ch.key,old:null,next:ch.value,nativeCreatedAttribute:true});}}
const intended=old.filter(r=>r.raw.trim()).map(r=>r.raw.replace(/\|$/,'')).join('|\n');
function protectedMap(s){const m={};for(const r of parse(s)){if(!r.h?.id)continue;const k=r.doc+'|'+r.h.type+'|'+r.h.id;if(r.d===null){delete m[k];continue;}if(r.doc===page&&r.h.type==='ATTR'&&changes.some(x=>x.parentId===r.d.parentId&&x.key===r.d.key))continue;m[k]=JSON.stringify(r.d);}return m;}
function delta(a,b){return [...new Set([...Object.keys(a),...Object.keys(b)])].filter(k=>a[k]!==b[k]);}
if(delta(protectedMap(original),protectedMap(intended)).length)throw new Error('Offline guard rejected source patch');
if(!await eda.sys_FileSystem.saveFileToFileSystem(root+'sch-metadata-sync-intended.epru',new Blob([intended]),undefined,true))throw new Error('Patch backup failed');
if(!await eda.sys_FileManager.setDocumentSource(intended))throw new Error('Native source update rejected');
const live=await eda.sys_FileManager.getDocumentSource(),bad=delta(protectedMap(original),protectedMap(live));
const report={checkedAt:new Date().toISOString(),method:'exact native source ATTR patch after guarded API normalization',page,changes:edits,protectedRecordDifferences:bad,protectedSourceUnchanged:bad.length===0,modifiesPcb:false,modifiesLibraries:false};
if(!await eda.sys_FileSystem.saveFileToFileSystem(root+'sch-after-metadata-sync.epru',new Blob([live]),undefined,true))throw new Error('After backup failed');
if(bad.length)throw new Error('Unexpected protected record changes '+JSON.stringify(bad));
report.saved=await eda.sch_Document.save();
if(!await eda.sys_FileSystem.saveFileToFileSystem(root+'sch-metadata-sync-final-report.json',new Blob([JSON.stringify(report,null,2)]),undefined,true))throw new Error('Report save failed');
if(report.saved!==true)throw new Error('Native save false; inspect actual state before close');
return report;
