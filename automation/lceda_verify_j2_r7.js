/* Read-only localized r7 replacement audit. args.kind='pcb'|'sch'.
 * Compares actual source data against fresh pre-replacement backups. Does not
 * infer manufacturing drill sizes from the component-pad getter, whose repeated
 * unit conversion is inconsistent with the preserved footprint source.
 */
const a=__CLI__.args||{},R='D:/Works/Calc/Calxus/engineering/';
const kind=a.kind||'pcb',isPcb=kind==='pcb';
const doc=isPcb?'2a0c39c6c6694f40':'0b9f8a9f53fb8264';
const oldId=isPcb?'bf0558871cf48b60':'464d839cd4909c9e';
const newId=isPcb?'b5596e790541d216':'1488a7a605462dd5';
const tab=await eda.dmt_EditorControl.openDocument(doc);await eda.dmt_EditorControl.activateDocument(tab);
if(!await eda.dmt_EditorControl.waitForDocumentReady(tab))throw new Error('Document not ready');
const info=await eda.dmt_SelectControl.getCurrentDocumentInfo();
if(info.parentProjectUuid!=='6f31bb473de1899361a57910c51c08e861ce117b8335b0b090c2886f654c0785')throw new Error('Wrong project');
const before=await (await eda.sys_FileSystem.readFileFromFileSystem(R+'r7-before-'+(isPcb?'pcb':'sch')+'-source.epru')).text();
const after=await eda.sys_FileManager.getDocumentSource();
function parse(s){let current;const m=new Map();for(const raw of s.split('\n')){if(!raw.trim())continue;const i=raw.indexOf('||');const h=JSON.parse(raw.slice(0,i)),body=raw.slice(i+2).replace(/\|\s*$/,'');const d=body&&body!=='|'?JSON.parse(body):null;if(h.type==='DOCHEAD'){current=d.uuid;continue;}if(current!==doc)continue;const key=h.type+':'+h.id;if(d===null)m.delete(key);else m.set(key,{h,d});}return m;}
function stable(o){if(Array.isArray(o))return o.map(stable);if(o&&typeof o==='object')return Object.fromEntries(Object.keys(o).sort().map(k=>[k,stable(o[k])]));return o;}
const b=parse(before),c=parse(after),excluded=[];
const shieldBranches={
 '73c2051c3a4592ff':[1650,-1090,1640,-1090],
 '156e15986572ff43':[1640,-1070,1640,-1090],
 'f4fb0f69e4a01946':[1640,-1070,1650,-1070],
 '954fffe2713e9e62':[1640,-1100,1640,-1090],
 '1653bb04b06c25b5':[1640,-1100,1650,-1100]
};
function protectedRecord(r){if(r.h.type==='ELE_PLACEHOLDER'){excluded.push(r.h.type+':'+r.h.id);return false;}if(String(r.h.id).includes(oldId)||String(r.h.id).includes(newId)||[oldId,newId].includes(r.d.parentId))return false;if(!isPcb&&r.h.type==='LINE'&&shieldBranches[r.h.id]){const d=r.d;if(d.lineGroup!=='10a24acfefb42433'||JSON.stringify([d.startX,d.startY,d.endX,d.endY])!==JSON.stringify(shieldBranches[r.h.id]))throw new Error('Shield branch differs '+r.h.id);return false;}return true;}
// The only authorized non-J2 PCB change is SW1's instance model Z offset.
if(isPcb){const sw=c.get('COMPONENT:4acc6f736faef614');if(sw?.d.attrs?.['3D Model Transform']==='590.55,218.5035,0,0,0,0,0,-38.031,-98.42496063')delete sw.d.attrs['3D Model Transform'];}
const approvedDrawOrderChanges=[];
if(!isPcb)for(const id of ['810494f61b9a8843','008896768b516b08']){const k='ATTR:'+id,old=b.get(k),now=c.get(k);if(old&&now&&old.d.zIndex!==now.d.zIndex){approvedDrawOrderChanges.push({id,field:'zIndex',before:old.d.zIndex,after:now.d.zIndex,reason:'Native wire-group child draw-order count grows when the two shield branches are added; coordinates, alignment, text and connectivity are compared unchanged.'});now.d.zIndex=old.d.zIndex;}}
const bp=new Map([...b].filter(([k,r])=>protectedRecord(r))),cp=new Map([...c].filter(([k,r])=>protectedRecord(r)));
const differences=[];
for(const [key,r]of bp){const n=cp.get(key);if(!n)differences.push({key,reason:'missing'});else if(JSON.stringify(stable(r.d))!==JSON.stringify(stable(n.d)))differences.push({key,reason:'changed',before:r.d,after:n.d});}
for(const key of cp.keys())if(!bp.has(key))differences.push({key,reason:'added',after:cp.get(key).d});
const report={checkedAt:new Date().toISOString(),kind,project:info.parentProjectUuid,document:doc,oldId,newId,protectedRecords:bp.size,differences,pass:differences.length===0,approvedDrawOrderChanges,
  approvedPcbModelOverride:isPcb?{reference:'SW1',field:'COMPONENT.attrs.3D Model Transform',value:'590.55,218.5035,0,0,0,0,0,-38.031,-98.42496063',deltaZmm:.5,sourceEvidence:'sw1-instance-model-r7.json'}:undefined,
  excludedNonGeometryCounters:[...new Set(excluded)]};
if(isPcb){report.counts=Object.fromEntries(['COMPONENT','LINE','VIA','POUR','REGION','LAYER_PHYS','PAD','POLY'].map(t=>[t,[...c.values()].filter(r=>r.h.type===t).length]));report.stackup=await eda.pcb_Layer.getStackup();report.J2=await eda.pcb_PrimitiveComponent.get(newId);const fp=await eda.lib_Footprint.getDocumentSource('27a835ea6dfc1a7f',info.parentProjectUuid);report.footprintPadSource=String(fp).split('\n').filter(x=>/^\{"type":"PAD"/.test(x));if(report.footprintPadSource.length!==6)throw new Error('Expected six exact footprint PAD records');report.drillSourceNote='Source records are authoritative: ROUND39.37mil, SLOT82.677x31.496mil relativeAngle90. Pad getter hole numbers have inconsistent unit scaling; do not use them as manufacturing drill dimensions. Final Excellon must independently confirm all six holes.';}
else {report.allowedGroundWireBefore=b.get('WIRE:10a24acfefb42433')?.d;report.allowedGroundWireAfter=c.get('WIRE:10a24acfefb42433')?.d;report.J2=await eda.sch_PrimitiveComponent.get(newId);let n=await eda.sch_Netlist.getNetlist('JLCEDA');if(typeof n==='string')n=JSON.parse(n);report.netlistCounts={components:Object.keys(n.components).length,pins:Object.values(n.components).reduce((s,x)=>s+Object.keys(x.pinInfoMap||{}).length,0)};report.J2Netlist=Object.values(n.components).find(x=>x.props?.Designator==='J2');}
if(!await eda.sys_FileSystem.saveFileToFileSystem(R+'j2-r7-'+kind+'-source-audit.json',new Blob([JSON.stringify(report,null,2)])))throw new Error('Audit save failed');
return {kind,pass:report.pass,protectedRecords:report.protectedRecords,differences:report.differences,counts:report.counts,netlistCounts:report.netlistCounts,J2Netlist:report.J2Netlist,reportPath:R+'j2-r7-'+kind+'-source-audit.json'};
