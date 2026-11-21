/* Native schematic readback after functional layout. No PCB import or mutation.
 * args.stage='audit'|'pdf'. Audit exports a compact actual pin-net list, ERC,
 * library metadata, and both API/source NC flags; PDF retains native ZIP name.
 */
const ROOT='D:/Works/Calc/Calxus/';
const args=__CLI__.args||{};
const stage=args.stage||'audit';
async function read(name){const f=await eda.sys_FileSystem.readFileFromFileSystem(ROOT+'engineering/'+name);if(!f)throw new Error('Missing '+name);return JSON.parse(await f.text());}
async function save(path,data){if(!await eda.sys_FileSystem.saveFileToFileSystem(ROOT+path,new Blob([typeof data==='string'?data:JSON.stringify(data,null,2)],{type:'application/json'})))throw new Error('Cannot save '+path);}
const binding=args.binding||await read(args.bindingFile||'eda-bindings.json');
if(args.projectUuid)binding.projectId=args.projectUuid;
const design=await read('design-input.json');
const plan=await read('functional-schematic-plan.json');
const pages=['01_USB_Power','02_TI_SilverLink','03_UART_Adapters'];
async function activate(page){const tab=await eda.dmt_EditorControl.openDocument(binding.pages[page]);await eda.dmt_EditorControl.activateDocument(tab);if(!await eda.dmt_EditorControl.waitForDocumentReady(tab))throw new Error('Page not ready '+page);const info=await eda.dmt_SelectControl.getCurrentDocumentInfo();if(info?.uuid!==binding.pages[page]||info.documentType!==1)throw new Error('Wrong active schematic page');if(args.projectUuid&&info.parentProjectUuid!==args.projectUuid)throw new Error('Schematic belongs to another project');return tab;}
function sourceDocuments(text){let current=null;const docs={};for(const raw of text.split('\n')){if(!raw.trim())continue;const cut=raw.indexOf('||');if(cut<0)throw new Error('Unknown source record');const h=JSON.parse(raw.slice(0,cut)),body=raw.slice(cut+2).replace(/\|\s*$/,'');const d=body===''||body==='|'?null:JSON.parse(body);if(h.type==='DOCHEAD'){current=d.uuid;docs[current]={head:d,records:new Map()};}else{const key=h.type+':'+h.id;if(d===null)docs[current].records.delete(key);else docs[current].records.set(key,{h,d});}}for(const doc of Object.values(docs))doc.records=[...doc.records.values()];return docs;}
function sourceAttributes(records){const attrs={};for(const {h,d}of records)if(h.type==='ATTR'){if(!attrs[d.parentId])attrs[d.parentId]={};attrs[d.parentId][d.key]=d.value;}return attrs;}
if(stage==='audit'){
  const nc=[],sourcePositions=[];
  for(const page of pages){
    await activate(page);
    if(args.saveBeforeAudit&&await eda.sch_Document.save()!==true)throw new Error('Native schematic save failed; audit cannot establish persistence. Keep the live document open and preserve its source.');
    await activate(page);const docs=sourceDocuments(await eda.sys_FileManager.getDocumentSource()),records=docs[binding.pages[page]]?.records;
    if(!records)throw new Error('Current page is absent from actual source');
    const sourceAttrs=sourceAttributes(records),componentsByRef={};
    for(const rec of records.filter(r=>r.h.type==='COMPONENT')){const ref=sourceAttrs[rec.h.id]?.Designator;if(ref)componentsByRef[ref]=rec;}
    for(const [ref,wanted]of Object.entries(plan.components).filter(([ref,p])=>p.sheet===page)){
      const component=componentsByRef[ref],id=component?.h.id;
      const actual=component?.d;
      sourcePositions.push({ref,primitiveId:id,page,expected:{x:wanted.x,y:wanted.y,rotation:0},actual:actual?{x:actual.x,y:-actual.y,rotation:actual.rotation||0,mirror:!!actual.isMirror}:null,pass:!!actual&&actual.x===wanted.x&&-actual.y===wanted.y&&(actual.rotation||0)===0&&!!actual.isMirror===!!wanted.mirror});
    }
    const attrs=records.filter(r=>r.h.type==='ATTR'&&r.d.key==='NO_CONNECT');
    for(const p of design.parts.filter(p=>!p.pcb_only&&p.sheet===page&&Object.values(p.pins).some(v=>v===null))){
      const c=componentsByRef[p.ref];if(!c)throw new Error('Missing actual component '+p.ref);
      await activate(page);const pins=await eda.sch_PrimitiveComponent.getAllPinsByPrimitiveId(c.h.id);
      for(const pin of pins){
        const number=String(pin.getState_PinNumber());if(p.pins[number]!==null)continue;
        // EPRJ3 getDocumentSource returns only this page, without library DOCHEADs.
        // Read the actual native component-pin ID instead of requiring embedded symbols.
        const pinId=String(pin.getState_PrimitiveId());
        const parentIds=[pinId,c.h.id+'-'+pinId,c.h.id+'.'+pinId];
        const matching=attrs.filter(a=>parentIds.includes(a.d.parentId));
        if(matching.length>1)throw new Error('Ambiguous source NC record '+p.ref+'.'+number);
        const attr=matching[0];
        const item={ref:p.ref,pin:number,page,componentId:c.h.id,pinId,apiNoConnected:pin.getState_NoConnected(),sourceValue:attr?.d.value??null};
        nc.push(item);
      }
    }
  }
  await activate(pages[0]);let netlist=await eda.sch_Netlist.getNetlist('JLCEDA');if(typeof netlist==='string')netlist=JSON.parse(netlist);
  const compact={version:netlist.version,components:{}};
  for(const [id,c]of Object.entries(netlist.components||{})){
    compact.components[id]={props:Object.fromEntries(['Designator','Supplier Part','Device','Footprint','Name'].map(k=>[k,c.props?.[k]??null])),pinInfoMap:Object.fromEntries(Object.entries(c.pinInfoMap||{}).map(([k,p])=>[k,{number:p.number,net:p.net}]))};
  }
  await activate(pages[0]);const drc=await eda.sch_Drc.check(false,false,true);
  const expected=design.parts.filter(p=>!p.pcb_only&&!p.ref.startsWith('TP'));
  const actual=Object.values(compact.components);
  const metadata=expected.map(p=>{const c=actual.find(c=>c.props.Designator===p.ref);return {ref:p.ref,found:!!c,devicePresent:!!c?.props.Device,footprintPresent:!!c?.props.Footprint,supplierPart:c?.props['Supplier Part'],expectedSupplierPart:p.footprint_lcsc||p.lcsc};});
  const report={checkedAt:new Date().toISOString(),scope:'Live document readback. Filesystem persistence and post-reload equivalence must be verified independently.',saveRequested:!!args.saveBeforeAudit,components:actual.length,pins:actual.reduce((n,c)=>n+Object.keys(c.pinInfoMap).length,0),sourcePositions,nc,metadata,drc};
  await save('engineering/schematic-netlist-functional.json',compact);
  await save('engineering/schematic-drc-functional.json',drc);
  await save('engineering/schematic-audit-functional.json',report);
  return {netlist:compact,report};
}
if(stage==='pdf'){
  await activate(pages[0]);
  const file=await eda.sch_ManufactureData.getExportDocumentFile('Calxus_RevA_schematic','PDF',undefined,'All Schematic',{outputMethod:'Merged sheet'});
  if(!file)throw new Error('No schematic PDF export returned');
  const path=ROOT+'exports/'+file.name;
  if(!await eda.sys_FileSystem.saveFileToFileSystem(path,file))throw new Error('Cannot save native schematic export');
  // This editor returns a ZIP even for merged PDF output. Keep the native ZIP
  // and extract its single PDF so an older ZIP mislabeled .pdf is corrected.
  const bytes=new Uint8Array(await file.arrayBuffer()),view=new DataView(bytes.buffer);
  let end=-1;for(let i=bytes.length-22;i>=Math.max(0,bytes.length-65557);i--)if(view.getUint32(i,true)===0x06054b50){end=i;break;}
  if(end<0)throw new Error('Native schematic export is not a ZIP');
  let cursor=view.getUint32(end+16,true);const entries=[];
  for(let i=0;i<view.getUint16(end+10,true);i++){
    if(view.getUint32(cursor,true)!==0x02014b50)throw new Error('Invalid ZIP directory');
    const nameLen=view.getUint16(cursor+28,true),extraLen=view.getUint16(cursor+30,true),commentLen=view.getUint16(cursor+32,true);
    const name=new TextDecoder().decode(bytes.slice(cursor+46,cursor+46+nameLen));
    entries.push({name,flags:view.getUint16(cursor+8,true),method:view.getUint16(cursor+10,true),crc:view.getUint32(cursor+16,true),compressed:view.getUint32(cursor+20,true),size:view.getUint32(cursor+24,true),offset:view.getUint32(cursor+42,true)});
    cursor+=46+nameLen+extraLen+commentLen;
  }
  const pdfs=entries.filter(e=>e.name.toLowerCase().endsWith('.pdf'));if(pdfs.length!==1)throw new Error('Expected one merged PDF, found '+pdfs.length);
  const entry=pdfs[0],off=entry.offset;if(entry.flags&1)throw new Error('Encrypted ZIP entry');
  if(view.getUint32(off,true)!==0x04034b50)throw new Error('Invalid local ZIP header');
  const start=off+30+view.getUint16(off+26,true)+view.getUint16(off+28,true),compressed=bytes.slice(start,start+entry.compressed);
  let pdf;
  if(entry.method===0)pdf=new Blob([compressed],{type:'application/pdf'});
  else if(entry.method===8){const reader=new Blob([compressed]).stream().pipeThrough(new DecompressionStream('deflate-raw')).getReader(),chunks=[];while(true){const r=await reader.read();if(r.done)break;chunks.push(r.value);}pdf=new Blob(chunks,{type:'application/pdf'});}
  else throw new Error('Unsupported ZIP compression '+entry.method);
  const decoded=new Uint8Array(await pdf.arrayBuffer());
  if(decoded.length!==entry.size||new TextDecoder().decode(decoded.slice(0,5))!=='%PDF-')throw new Error('PDF header/size mismatch');
  let crc=0xffffffff;for(const byte of decoded){crc^=byte;for(let k=0;k<8;k++)crc=(crc>>>1)^((crc&1)?0xedb88320:0);}crc=(crc^0xffffffff)>>>0;
  if(crc!==entry.crc)throw new Error('ZIP PDF CRC mismatch');
  const pdfPath=ROOT+'exports/Calxus_RevA_schematic.pdf';if(!await eda.sys_FileSystem.saveFileToFileSystem(pdfPath,pdf))throw new Error('Cannot save extracted PDF');
  return {path,name:file.name,size:file.size,type:file.type,pdfPath,pdfSize:pdf.size,pdfEntry:entry.name,pdfCrc32:crc.toString(16)};
}
throw new Error('Unknown stage '+stage);
