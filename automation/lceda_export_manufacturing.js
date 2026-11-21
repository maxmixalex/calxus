/* Native, one-export-per-invoke manufacturing handoff. Root owns execution.
 * args: {stage:'export', kind:'project'|'gerber'|'bom'|'cpl'|'step-board'|'step-full'|'pdf',
 *        projectUuid?, pcbId?, schematicPageId?, root?, exportDir?, baseName?,
 *        requireActiveDocument?:true}
 * No schematic-to-PCB import. No mutation of design geometry. Every canvas
 * export opens, activates, waits and verifies its actual document identity.
 * Undefined/empty exports are failures and never create placeholder files.
 */
const args=__CLI__.args||{};
const ROOT=(args.root||'D:/Works/Calc/Calxus/').replace(/\/?$/,'/');
const OUT=(args.exportDir||ROOT+'exports/').replace(/\/?$/,'/');
const kind=args.kind||(args.stage&&args.stage!=='export'?args.stage:'project');
const base=args.baseName||'Calxus_RevA';
if(!['project','gerber','bom','cpl','step-board','step-full','pdf'].includes(kind))throw new Error('Unknown export kind '+kind);
if(/[\\/]/.test(base))throw new Error('baseName must not contain a path');
async function readJSON(name){const f=await eda.sys_FileSystem.readFileFromFileSystem(ROOT+'engineering/'+name);return f?JSON.parse(await f.text()):null;}
const binding=await readJSON(args.bindingFile||'eda-bindings.json')||{};
const projectUuid=args.projectUuid||binding.projectUuid||binding.projectId;
const pcbId=args.pcbId||binding.pcbId||binding.pcbUuid||'2a0c39c6c6694f40';
const pageId=args.schematicPageId||binding.pages?.['01_USB_Power'];
const result={ok:false,kind,checkedAt:new Date().toISOString(),requested:{projectUuid,pcbId,schematicPageId:pageId},files:[],failures:[]};

async function activate(uuid,type){
  if(!uuid)throw new Error('Missing document UUID for '+kind);
  // For cache-sensitive exports, activate in a previous, completed invocation,
  // verify the document in another, then use this branch for export only.
  if(args.requireActiveDocument===true){
    const current=await eda.dmt_SelectControl.getCurrentDocumentInfo();
    if(current?.uuid!==uuid||current.documentType!==type||
       (projectUuid&&current.parentProjectUuid!==projectUuid))
      throw new Error('Required document is not already active: '+JSON.stringify(current));
    result.activeDocument=current;
    result.activationMode='previous_completed_invocation';
    return current.tabId;
  }
  const tab=await eda.dmt_EditorControl.openDocument(uuid);
  await eda.dmt_EditorControl.activateDocument(tab);
  if(!await eda.dmt_EditorControl.waitForDocumentReady(tab))throw new Error('Document did not become ready '+uuid);
  const current=await eda.dmt_SelectControl.getCurrentDocumentInfo();
  if(current?.uuid!==uuid||current.documentType!==type)throw new Error('Wrong active document: '+JSON.stringify(current));
  if(projectUuid&&current.parentProjectUuid!==projectUuid)throw new Error('Active document belongs to another project; pass the imported project UUID explicitly');
  result.activeDocument=current;
  return tab;
}
function safeName(name,fallback){
  const candidate=String(name||fallback).split(/[\\/]/).pop();
  if(!candidate||candidate==='.'||candidate==='..')throw new Error('Invalid exported filename');
  return candidate;
}
async function classify(file){
  const head=new Uint8Array(await file.slice(0,256).arrayBuffer());
  const text=new TextDecoder().decode(head);
  if(head[0]===0x50&&head[1]===0x4b)return {format:'zip'};
  if(text.startsWith('%PDF-'))return {format:'pdf'};
  if(text.trimStart().startsWith('ISO-10303-21;'))return {format:'step'};
  if(head[0]===0xff&&head[1]===0xfe){
    const sample=new TextDecoder('utf-16le').decode(await file.slice(0,16384).arrayBuffer());
    return {format:sample.split(/\r?\n/)[0].includes('\t')?'tsv':'csv',encoding:'utf-16le',bom:true};
  }
  if(kind==='bom'||kind==='cpl'){
    const sample=new TextDecoder('utf-8',{fatal:true}).decode(await file.slice(0,16384).arrayBuffer());
    return {format:sample.split(/\r?\n/)[0].includes('\t')?'tsv':'csv',encoding:'utf-8',bom:head[0]===0xef&&head[1]===0xbb};
  }
  return {format:'unknown',magic:Array.from(head.slice(0,16))};
}
async function persist(file,name,details={}){
  if(!file||typeof file.arrayBuffer!=='function'||!Number.isFinite(file.size)||file.size<=0)throw new Error('Export returned undefined or empty file: '+kind);
  const path=OUT+safeName(name,file.name);
  // The official CLI guide documents force=true as the fourth argument.
  const saved=await eda.sys_FileSystem.saveFileToFileSystem(path,file,undefined,true);
  const item={path,nativeName:file.name||null,size:file.size,type:file.type||'',saved:saved===true,...details};
  result.files.push(item);
  if(saved!==true)throw new Error('Filesystem write returned false: '+path);
  if(file.size<=8*1024*1024){
    const readback=await eda.sys_FileSystem.readFileFromFileSystem(path);
    if(!readback)throw new Error('Saved file cannot be read: '+path);
    const actual=new Uint8Array(await readback.arrayBuffer()),expected=new Uint8Array(await file.arrayBuffer());
    let same=actual.length===expected.length;
    if(same)for(let i=0;i<actual.length;i++)if(actual[i]!==expected[i]){same=false;break;}
    item.readbackBytes=actual.length;item.readbackByteIdentical=same;
    if(!same)throw new Error('Saved file byte readback mismatch: '+path);
  }else{
    item.readbackByteIdentical=null;
    item.readbackNote='Large native FileSystem reads are unreliable in this client; accompanying gzip is verified separately.';
  }
  return item;
}
async function gzip(file,name){
  const reader=file.stream().pipeThrough(new CompressionStream('gzip')).getReader(),chunks=[];
  while(true){const x=await reader.read();if(x.done)break;chunks.push(x.value);}
  const compressed=new Blob(chunks,{type:'application/gzip'});
  return persist(compressed,name,{format:'gzip',originalBytes:file.size});
}
async function extractMergedPdf(file){
  const bytes=new Uint8Array(await file.arrayBuffer()),view=new DataView(bytes.buffer);
  let end=-1;
  for(let i=bytes.length-22;i>=Math.max(0,bytes.length-65557);i--)if(view.getUint32(i,true)===0x06054b50){end=i;break;}
  if(end<0)throw new Error('PDF ZIP end directory missing');
  let cursor=view.getUint32(end+16,true);const entries=[];
  for(let i=0;i<view.getUint16(end+10,true);i++){
    if(view.getUint32(cursor,true)!==0x02014b50)throw new Error('Invalid PDF ZIP directory');
    const n=view.getUint16(cursor+28,true),e=view.getUint16(cursor+30,true),c=view.getUint16(cursor+32,true);
    entries.push({name:new TextDecoder().decode(bytes.slice(cursor+46,cursor+46+n)),flags:view.getUint16(cursor+8,true),method:view.getUint16(cursor+10,true),crc:view.getUint32(cursor+16,true),compressed:view.getUint32(cursor+20,true),size:view.getUint32(cursor+24,true),offset:view.getUint32(cursor+42,true)});
    cursor+=46+n+e+c;
  }
  const pdfs=entries.filter(x=>x.name.toLowerCase().endsWith('.pdf'));
  if(pdfs.length!==1)throw new Error('Expected exactly one merged PDF, found '+pdfs.length);
  const e=pdfs[0],off=e.offset;
  if(e.flags&1||view.getUint32(off,true)!==0x04034b50)throw new Error('Encrypted/invalid PDF ZIP entry');
  const start=off+30+view.getUint16(off+26,true)+view.getUint16(off+28,true),compressed=bytes.slice(start,start+e.compressed);
  let pdf;
  if(e.method===0)pdf=new Blob([compressed],{type:'application/pdf'});
  else if(e.method===8){const reader=new Blob([compressed]).stream().pipeThrough(new DecompressionStream('deflate-raw')).getReader(),chunks=[];while(true){const x=await reader.read();if(x.done)break;chunks.push(x.value);}pdf=new Blob(chunks,{type:'application/pdf'});}
  else throw new Error('Unsupported PDF ZIP compression '+e.method);
  const data=new Uint8Array(await pdf.arrayBuffer());
  if(data.length!==e.size||new TextDecoder().decode(data.slice(0,5))!=='%PDF-')throw new Error('Extracted PDF header/size mismatch');
  let crc=0xffffffff;for(const b of data){crc^=b;for(let i=0;i<8;i++)crc=(crc>>>1)^((crc&1)?0xedb88320:0);}crc=(crc^0xffffffff)>>>0;
  if(crc!==e.crc)throw new Error('Extracted PDF CRC mismatch');
  return persist(pdf,base+'_schematic.pdf',{format:'pdf',zipEntry:e.name,crc32:crc.toString(16)});
}
try{
  let file;
  if(kind==='project'){
    if(!projectUuid)throw new Error('Pass actual projectUuid, especially after EPRJ3 import');
    file=await eda.sys_FileManager.getProjectFileByProjectUuid(projectUuid,base,undefined,'epro2');
  }else if(kind==='pdf'){
    await activate(pageId,1);
    file=await eda.sch_ManufactureData.getExportDocumentFile(base+'_schematic','PDF',undefined,'All Schematic',{outputMethod:'Merged sheet'});
  }else{
    await activate(pcbId,3);
    if(kind==='gerber')file=await eda.pcb_ManufactureData.getGerberFile(base+'_Gerber',false,'mm',{integerNumber:4,decimalNumber:5},{metallicDrillingInformation:true,nonMetallicDrillingInformation:true,drillTable:true,flyingProbeTestingFile:true});
    if(kind==='bom'){
      const props=['Designator','Name','Footprint','Supplier Part','Manufacturer Part','JLCPCB Part Class'];
      const columns=['Designator','Quantity','Name','Footprint','Supplier Part','Manufacturer Part','JLCPCB Part Class'].map((property,i)=>({property,title:property,sort:property==='Designator'?'asc':null,group:['Footprint','Supplier Part','Manufacturer Part','Name','JLCPCB Part Class'].includes(property)?'Yes':'No',orderWeight:100-i}));
      // Client 4.1.105 returned only 4 of the 93 physical parts for the documented
      // string-valued "yes" filter. Export the complete native BOM, then select
      // the reviewed 87 SMT references with tools/prepare_smt_files.py.
      result.bomFilter=[];
      result.bomRequiresSubsetValidation=true;
      file=await eda.pcb_ManufactureData.getBomFile(base+'_BOM_native','csv',undefined,[],['Quantity'],props,columns);
    }
    if(kind==='cpl')file=await eda.pcb_ManufactureData.getPickAndPlaceFile(base+'_CPL_native','csv','mm');
    if(kind==='step-board'||kind==='step-full'){
      const elements=kind==='step-board'?[]:(args.stepElements||['Component Model']);
      result.stepElements=elements;
      result.stepGeometryScopeVerified=false;
      result.stepScopeNote=kind==='step-board'
        ?'Requested an empty optional-element list with automatic models disabled. The API does not explicitly document empty-array behavior; inspect the actual STEP product/solid list and identify the Board before claiming board-only geometry.'
        :'Requested component models. Inspect the actual STEP products/solids, placements and unavailable models before treating it as a complete assembly.';
      file=await eda.pcb_ManufactureData.get3DFile(base+(kind==='step-board'?'_board':'_PCBA'),'step',elements,'Outfit',kind==='step-full');
    }
  }
  if(!file||file.size<=0)throw new Error('Native export returned undefined or zero bytes for '+kind);
  const format=await classify(file);
  if((kind==='project'||kind==='gerber')&&format.format!=='zip')throw new Error('Native archive does not have ZIP magic');
  if(kind.startsWith('step-')&&format.format!=='step')throw new Error('Native STEP export has unexpected magic');
  if(kind==='pdf'&&!['zip','pdf'].includes(format.format))throw new Error('Native PDF export has unexpected magic');
  let filename=safeName(file.name,base+'_'+kind);
  if(kind==='project')filename=base+'.epro2';
  if(kind==='gerber'&&!filename.toLowerCase().endsWith('.zip'))filename+='.zip';
  if(kind==='pdf')filename=base+'_schematic.'+format.format;
  if(kind==='bom'||kind==='cpl')filename=base+'_'+kind.toUpperCase()+'_native.'+format.format;
  if(kind.startsWith('step-')&&!/\.(step|stp)$/i.test(filename))filename+='.step';
  await persist(file,filename,format);
  if(kind==='pdf'&&format.format==='zip')await extractMergedPdf(file);
  if(kind.startsWith('step-'))await gzip(file,filename+'.gz');
  result.ok=true;
}catch(error){result.failures.push({kind,message:String(error?.message||error),undefinedOrEmpty:/undefined|zero bytes|empty file/.test(String(error?.message||error))});}
result.finishedAt=new Date().toISOString();
const manifestPath=OUT+base+'_'+kind+'_export-report.json';
const manifestSaved=await eda.sys_FileSystem.saveFileToFileSystem(manifestPath,new Blob([JSON.stringify(result,null,2)],{type:'application/json'}),undefined,true);
if(manifestSaved!==true){result.ok=false;result.failures.push({kind:'manifest',message:'Failed to save export report'});}
return {...result,manifestPath,manifestSaved:manifestSaved===true};
