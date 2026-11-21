/* Calxus native JLCEDA engineering build. Run with lceda-pro invoke --code-file.
 * args: {stage:'place'|'wire'|'nc'|'netlist', offset:0, limit:12, page?:string}
 * This script never orders parts or boards. State is persisted after each part.
 */
const ROOT = 'D:/Works/Calc/Calxus/engineering/';
const arg = __CLI__.args || {};
async function read(name, fallback) {
  const f = await eda.sys_FileSystem.readFileFromFileSystem(ROOT + name);
  if (!f) return fallback;
  const data = JSON.parse(await f.text());
  if (data && data.success === false && data.code) {
    if (fallback !== undefined) return fallback;
    throw new Error('Cannot read ' + name + ': ' + data.message);
  }
  return data;
}
async function write(name, object) {
  const ok = await eda.sys_FileSystem.saveFileToFileSystem(ROOT + name,
    new Blob([JSON.stringify(object, null, 2)], {type:'application/json'}));
  if (!ok) throw new Error('Cannot save ' + name);
}
function unwrap(result, context) {
  if (!result?.ok) throw new Error(context + ': ' + JSON.stringify(result));
  return result.value;
}
const design = await read('design-input.json');
const catalog = await read('library-cache.json');
const binding = await read('eda-bindings.json');
const state = await read('placement-state.json', {components:{}, wires:{}, noConnect:{}});
const parts = design.parts.filter(p => !p.pcb_only && !p.ref.startsWith('TP'));
const source = pageName => ({projectId:binding.projectId, schematicName:binding.schematicName, pageName});
const result = [];
if (arg.stage === 'place') {
  for (const p of parts.slice(arg.offset || 0, (arg.offset || 0) + (arg.limit || 12))) {
    const lib = catalog[p.footprint_lcsc || p.lcsc];
    if (!lib || lib.error) throw new Error('No verified library for ' + p.ref + ': ' + p.lcsc);
    const expected = Object.keys(p.pins).sort();
    const actual = [...new Set(lib.symbol.pins.map(x => String(x.pinNumber)))].sort();
    const missing = expected.filter(x => !actual.includes(x));
    if (missing.length) throw new Error(p.ref + ' has missing symbol pins ' + missing.join(','));
    const pageParts = parts.filter(q => q.sheet === p.sheet);
    const index = pageParts.findIndex(q => q.ref === p.ref);
    const xy = p.sch_final_xy || [180 + (index % 7) * 310, 210 + Math.floor(index / 7) * 215];
    const known = state.components[p.ref] || binding.components[p.ref];
    let item;
    const props = {Name:lib.device.otherProperty?.Name || p.value, 'Calxus Function':p.note || '',
      'Add into BOM':p.assembly === 'pad-only' || p.pad_only || p.ref === 'J3' || p.ref === 'J4' || p.ref === 'J5' ? 'no' : 'yes'};
    if (known) {
      item = unwrap(await eda.sch_SourcePrimitiveComponent.update({...source(p.sheet),
        primitiveId:known.primitiveId, x:xy[0], y:xy[1], rotation:0, properties:props}), p.ref);
      item = {...known, ...item};
    } else {
      item = unwrap(await eda.sch_SourcePrimitiveComponent.add({...source(p.sheet),
        libraryUuid:lib.device.libraryUuid, name:lib.device.name,
        x:xy[0], y:xy[1], rotation:0, designator:p.ref}), p.ref);
      unwrap(await eda.sch_SourcePrimitiveComponent.update({...source(p.sheet),
        primitiveId:item.primitiveId, properties:props}), p.ref + ' properties');
    }
    // C456017's library symbol points its data pins left. The reviewed Calxus
    // drawing explicitly mirrors it to retain the four existing signal stubs.
    if (p.sch_mirror) {
      const tab=await eda.dmt_EditorControl.openDocument(binding.pages[p.sheet]);
      await eda.dmt_EditorControl.activateDocument(tab);
      if(!await eda.dmt_EditorControl.waitForDocumentReady(tab))throw new Error('Page not ready '+p.sheet);
      await eda.sch_PrimitiveComponent.modify(item.primitiveId,{mirror:true});
    }
    const geometry = unwrap(await eda.sch_SourcePin.getGeometry({...source(p.sheet), primitiveId:item.primitiveId}), p.ref+' geometry');
    state.components[p.ref] = {...item, page:p.sheet, xy, libraryId:p.footprint_lcsc || p.lcsc, geometry};
    await write('placement-state.json', state);
    result.push({ref:p.ref, primitiveId:item.primitiveId, pins:geometry.length, xy});
  }
} else if (arg.stage === 'wire') {
  for (const p of parts.slice(arg.offset || 0, (arg.offset || 0) + (arg.limit || 8))) {
    if (state.wires[p.ref]) {result.push({ref:p.ref, skipped:true}); continue;}
    const comp = state.components[p.ref];
    if (!comp) throw new Error('Unplaced ' + p.ref);
    let n = 0;
    for (const pin of comp.geometry) {
      const net = p.pins[String(pin.pinNumber)];
      if (!net) continue;
      let dx=0,dy=0;
      const side=String(pin.side).toLowerCase();
      if(side==='left') dx=-40;
      else if(side==='right') dx=40;
      else if(side==='top') dy=40;
      else if(side==='bottom') dy=-40;
      else throw new Error('Unknown side '+p.ref+'.'+pin.pinNumber+': '+pin.side);
      const wire = await eda.sch_SourcePrimitiveWire.add({...source(p.sheet),
        line:[pin.x,pin.y,pin.x+dx,pin.y+dy], net});
      unwrap(wire,p.ref+'.'+pin.pinNumber+' '+net);
      n++;
    }
    state.wires[p.ref] = {count:n, when:new Date().toISOString()};
    await write('placement-state.json', state);
    result.push({ref:p.ref,wires:n});
  }
} else if (arg.stage === 'nc') {
  const page = arg.page;
  const tab = await eda.dmt_EditorControl.openDocument(binding.pages[page]);
  await eda.dmt_EditorControl.activateDocument(tab);
  if (!await eda.dmt_EditorControl.waitForDocumentReady(tab)) throw new Error('Page not ready');
  await eda.dmt_Schematic.modifySchematicPageTitleBlock(true,{Size:{showTitle:true,showValue:true,value:'A2'}});
  for (const p of parts.filter(x=>x.sheet===page)) {
    const c=state.components[p.ref];
    if(!c) continue;
    const pins=await eda.sch_PrimitiveComponent.getAllPinsByPrimitiveId(c.primitiveId);
    let n=0;
    for(const pin of pins) {
      const num=String(pin.getState_PinNumber());
      if(p.pins[num]===null) {await eda.sch_PrimitivePin.modify(pin,{noConnected:true});n++;}
    }
    state.noConnect[p.ref]=n;
    result.push({ref:p.ref,noConnect:n});
  }
  await eda.sch_Document.save();
  await write('placement-state.json',state);
} else if (arg.stage === 'netlist') {
  const tab=await eda.dmt_EditorControl.openDocument(binding.pages['01_USB_Power']);
  await eda.dmt_EditorControl.activateDocument(tab);
  if (!await eda.dmt_EditorControl.waitForDocumentReady(tab)) throw new Error('Page not ready');
  const netlist=await eda.sch_Netlist.getNetlist('JLCEDA');
  await eda.sys_FileSystem.saveFileToFileSystem(ROOT+'schematic-netlist.json',new Blob([typeof netlist==='string'?netlist:JSON.stringify(netlist)],{type:'application/json'}));
  return {netlist};
} else throw new Error('Unknown build stage '+arg.stage);
return {stage:arg.stage, count:result.length, total:parts.length, result};
