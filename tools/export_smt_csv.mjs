import fs from 'node:fs/promises';
import path from 'node:path';
import { Workbook } from '@oai/artifact-tool';

const [input, destination] = process.argv.slice(2);
if (!input || !destination) throw new Error('Usage: export_smt_csv.mjs validated-tables.json output-directory');
const data = JSON.parse(await fs.readFile(input, 'utf8'));
if (data.validation?.pass !== true || data.validation.smt_count !== 87) throw new Error('A passing native 87-SMT validation is required');
await fs.mkdir(destination, { recursive: true });
const workbook = Workbook.create();
for (const name of ['bom', 'cpl']) {
  const table = data[name];
  if (!table?.length || table.some(row => row.length !== 5)) throw new Error('Invalid validated table');
  const sheet = workbook.worksheets.add(name.toUpperCase());
  sheet.getRange(`A1:E${table.length}`).values = table;
  sheet.showGridLines = false;
  sheet.getRange(`A1:E${table.length}`).format.font = {name:'Arial',size:10};
  sheet.getRange(`A1:E${table.length}`).format.rowHeight = 24;
  sheet.getRange('A1:E1').format = {fill:'#243746',font:{name:'Arial',size:10,bold:true,color:'#FFFFFF'}};
  const widths = name === 'bom' ? [270,520,420,150,90] : [130,150,150,100,120];
  widths.forEach((width,i) => { sheet.getRangeByIndexes(0,i,table.length,1).format.columnWidthPx = width; });
  if (name === 'cpl') sheet.getRange(`D2:D${table.length}`).format.horizontalAlignment = 'center';
}
workbook.recalculate();
const inspection = await workbook.inspect({kind:'table', range:'BOM!A1:E6', maxChars:3500, tableMaxRows:6, tableMaxCols:5});
await fs.writeFile(path.join(destination, 'smt-workbook-inspection.json'), JSON.stringify(inspection, null, 2));
const csvCell = value => {
  const text = value === null || value === undefined ? '' : String(value);
  return /[",\r\n]/.test(text) ? '"'+text.replaceAll('"','""')+'"' : text;
};
for (const name of ['bom', 'cpl']) {
  const sheet = workbook.worksheets.getItem(name.toUpperCase());
  const values = sheet.getRange(`A1:E${data[name].length}`).values;
  if (JSON.stringify(values) !== JSON.stringify(data[name])) throw new Error(`${name} changed during workbook authoring`);
  const csv = values.map(row => row.map(csvCell).join(',')).join('\r\n')+'\r\n';
  await fs.writeFile(path.join(destination, `Calxus_RevA_SMT_${name.toUpperCase()}.csv`), '\ufeff'+csv);
  const preview = await workbook.render({sheetName:name.toUpperCase(), range:`A1:E${Math.min(values.length,7)}`, scale:1.5});
  await fs.writeFile(path.join(destination, `smt-${name}-preview.png`), new Uint8Array(await preview.arrayBuffer()));
}
await fs.writeFile(path.join(destination, 'smt-native-export-validation.json'), JSON.stringify(data.validation,null,2)+'\n');
console.log(JSON.stringify({pass:true,smt:87,bomRows:data.bom.length-1,cplRows:data.cpl.length-1,destination}));
