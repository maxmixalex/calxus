/* Historical, isolated diagnostic-copy experiment. Not a canonical repair or
 * routine release step. Fixed copy project guard prevents use on original.
 * See validation/native-netlist-reference-diagnostic.json for observed outcome. */
const P='f4164eed1d531b75438df32f8fdbd7fef0b9cabbcc8488f73581ff7dd5c05855',R='D:/Works/Calc/Calxus/engineering/';
const active=await eda.dmt_SelectControl.getCurrentDocumentInfo(),project=await eda.dmt_Project.getCurrentProjectInfo();if(active.parentProjectUuid!==P||project.uuid!==P||active.uuid!=='2a0c39c6c6694f40'||active.tabId!=='2a0c39c6c6694f40@'+P)throw Error('Wrong isolated copy');
async function save(n,s){if(!await eda.sys_FileSystem.saveFileToFileSystem(R+n,new Blob([typeof s==='string'?s:JSON.stringify(s,null,2)]),undefined,true))throw Error('write');}
function rows(s){const r=new Map();for(const l of s.split(/\r?\n/)){const i=l.indexOf('||');if(i<0)continue;let h,d;try{h=JSON.parse(l.slice(0,i));const b=l.slice(i+2).trim().replace(/\|$/,'');d=b?JSON.parse(b):null;}catch{continue;}const k=h.type+'|'+h.id;if(d===null)r.delete(k);else r.set(k,{h,d});}return r;}
const before=await(await eda.sys_FileSystem.readFileFromFileSystem(R+'diagnostic-copy-before.epcb2')).text(),own=await(await eda.sys_FileSystem.readFileFromFileSystem(R+'diagnostic-copy-own-netlist.enet')).text();
const current=await eda.sys_FileManager.getDocumentSource();const b=rows(before),c=rows(current);for(const[k,v]of b)if(v.h.type!=='DOCHEAD'&&JSON.stringify(v.d)!==JSON.stringify(c.get(k)?.d))throw Error('Capture changed '+k);
await save('diagnostic-copy-setnetlist-pending.json',{at:new Date().toISOString(),source:'official-ECO',projectUuid:P});
const rawBefore=await eda.pcb_Drc.check(true,false,true);await save('diagnostic-copy-pre-eco.epcb2',current);await save('diagnostic-copy-before-eco-drc.json',rawBefore);const setResult=await eda.pcb_Document.importChanges('992d265f851ac884');const after=await eda.sys_FileManager.getDocumentSource();await save('diagnostic-copy-after-eco.epcb2',after);
const ar=rows(after),diff=[];for(const k of new Set([...b.keys(),...ar.keys()])){const bv=b.get(k),av=ar.get(k);if(JSON.stringify(bv?.d)!==JSON.stringify(av?.d))diff.push({key:k,type:bv?.h.type??av?.h.type,before:bv?.d,after:av?.d});}
const protectedTypes=new Set(['COMPONENT','ATTR','PAD','PAD_NET','LINE','VIA','REGION','LAYER','LAYER_PHYS','RULE_TEMPLATE','RULE','RULE_SELECTOR','NET','POUR','POURED','POLY','PRIMITIVE','STRING','SILK_OPTS','D3_ATTRIBUTE']);
const violations=diff.filter(x=>protectedTypes.has(x.type));let saved=false;if(setResult===true&&!violations.length)saved=await eda.pcb_Document.save();
const drc=await eda.pcb_Drc.check(true,false,true);const compare=await eda.sys_Tool.netlistComparison({projectUuid:P,documentUuid:'992d265f851ac884'},{projectUuid:P,documentUuid:'2a0c39c6c6694f40'});
const report={at:new Date().toISOString(),projectUuid:P,active,rawBefore,operation:'pcb_Document.importChanges',setResult,saved,protectedDifferences:violations,allDifferences:diff,drc,compare};await save('diagnostic-copy-eco-result.json',report);
return {setResult,saved,protectedDifferenceCount:violations.length,allDifferenceTypes:diff.map(x=>x.type),protectedDifferences:violations.slice(0,5),groups:drc.map(x=>({name:x.name,count:x.count})),comparisonCount:compare.length,comparisonSample:compare.slice(0,2)};
