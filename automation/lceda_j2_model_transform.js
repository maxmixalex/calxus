/* J2 instance-only model Z correction; operates on the already-active PCB.
 * args.stage='read' (default) | 'apply'. Never opens or activates a document.
 * SW1 native readback proved PCB_PrimitiveComponent.modify(otherProperty)
 * stores this override. Project-owned lib_Device.get fails for offline EPRJ3.
 */
const args=__CLI__.args||{},stage=args.stage||'read';
const project=args.projectUuid||'6f31bb473de1899361a57910c51c08e861ce117b8335b0b090c2886f654c0785';
const pcb=args.pcbUuid||'2a0c39c6c6694f40',primitiveId=args.primitiveId||'b5596e790541d216';
const key='3D Model Transform',old='562.991,393.7,0,0,0,0,-0.001,-157.48,-98.425',next='562.991,393.7,0,0,0,0,-0.001,-157.48,-94.487992126';
const info=await eda.dmt_SelectControl.getCurrentDocumentInfo();
if(info?.uuid!==pcb||info.parentProjectUuid!==project)throw new Error('Expected already-active r7 PCB; no document switch was attempted');
function components(source){let doc;const records=new Map();for(const raw of source.split('\n')){if(!raw.trim())continue;const i=raw.indexOf('||');if(i<0)throw new Error('Unexpected native source');const h=JSON.parse(raw.slice(0,i)),body=raw.slice(i+2).replace(/\|\s*$/,'');const d=body&&body!=='|'?JSON.parse(body):null;if(h.type==='DOCHEAD')doc=d?.uuid;if(doc===pcb&&h.type==='COMPONENT'){if(d===null)records.delete(h.id);else records.set(h.id,d);}}return records;}
function stable(x){if(Array.isArray(x))return x.map(stable);if(x&&typeof x==='object')return Object.fromEntries(Object.keys(x).sort().map(k=>[k,stable(x[k])]));return x;}
function protectedComponent(x){x=JSON.parse(JSON.stringify(x));if(x.attrs)delete x.attrs[key];return JSON.stringify(stable(x));}
const sourceBefore=await eda.sys_FileManager.getDocumentSource(),beforeRecord=components(sourceBefore).get(primitiveId);
const component=await eda.pcb_PrimitiveComponent.get(primitiveId);
if(!component||component.getState_Designator()!=='J2')throw new Error('Wrong J2 primitive');
const other=component.getState_OtherProperty()||{},current=beforeRecord?.attrs?.[key]??other[key];
if(![old,next].includes(current))throw new Error('Unexpected J2 model transform: '+current);
if(component.getState_SupplierId()!=='C456017')throw new Error('Wrong J2 part');
const summary={stage,project,pcb,primitiveId,current,old,new:next,deltaModelZmm:.1,changesRealPcbXY:false,changesFootprint:false,nativeRenderedStepVerified:false};
if(stage==='read')return summary;
if(stage!=='apply')throw new Error('Unsupported stage');
if(current===next)return {...summary,changed:false,nativeSourceReadbackMatches:true};
const backup='D:/Works/Calc/Calxus/engineering/j2-before-instance-model.epru';
if(!await eda.sys_FileSystem.saveFileToFileSystem(backup,new Blob([sourceBefore])))throw new Error('Native source backup failed');
await eda.pcb_PrimitiveComponent.modify(primitiveId,{otherProperty:{...other,[key]:next}});
const refreshed=await eda.pcb_PrimitiveComponent.get(primitiveId),sourceAfter=await eda.sys_FileManager.getDocumentSource();
const afterRecord=components(sourceAfter).get(primitiveId);
if(afterRecord?.attrs?.[key]!==next)throw new Error('Native COMPONENT.attrs did not retain the model transform');
if(protectedComponent(beforeRecord)!==protectedComponent(afterRecord))throw new Error('Protected J2 instance geometry/metadata changed');
if(refreshed.getState_Designator()!=='J2')throw new Error('Lost J2 instance');
const saved=await eda.pcb_Document.save();
if(!saved)throw new Error('Stored transform but native save returned false; inspect before continuing');
return {...summary,changed:true,backup,saved,nativeSourceReadbackMatches:true,protectedComponentUnchanged:true,nextVerification:'Export fresh native PCBA STEP and measure J2 mount feet/body. Stored source override alone does not prove renderer adoption.'};
