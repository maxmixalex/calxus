#!/usr/bin/env node
/* Render actual inspect_gerber.py SVGs with librsvg, including Gerbonara's
 * feColorMatrix/feComposite filters. CairoSVG omits those filters and produced
 * misleading monochrome composite views in the native export investigation.
 * This creates review images; a person must still inspect their contents. */
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const sharp = require('sharp');

async function main() {
  const directory = process.argv[2];
  if (!directory) throw new Error('Usage: node tools/render_gerber_previews.cjs validation/final-gerber');
  const images = [];
  for (const name of ['gerber-top', 'gerber-bottom', 'gerber-top-paste']) {
    const input = path.join(directory, name + '.svg');
    const output = path.join(directory, name + '.png');
    const svg = fs.readFileSync(input);
    const png = await sharp(svg, { density: 600 })
      .resize({ width: 2400 }).flatten({ background: '#ffffff' }).png().toBuffer();
    const metadata = await sharp(png).metadata();
    const statistics = await sharp(png).stats();
    if (metadata.width !== 2400 || metadata.height < 500 || statistics.entropy < 0.05)
      throw new Error('Blank or invalid Gerber rendering: ' + name);
    fs.writeFileSync(output, png);
    images.push({ file: path.basename(output), width: metadata.width, height: metadata.height,
      bytes: png.length, sha256: crypto.createHash('sha256').update(png).digest('hex'),
      svg_sha256: crypto.createHash('sha256').update(svg).digest('hex') });
  }
  const report = { renderer: 'Sharp/librsvg', versions: sharp.versions,
    scope: 'Actual CAM-derived SVG rasterization only; visual acceptance is recorded separately', images };
  fs.writeFileSync(path.join(directory, 'rendering.json'), JSON.stringify(report, null, 2) + '\n');
  console.log(JSON.stringify({ images: images.map(x => ({file:x.file,sha256:x.sha256})), visual_review_required: true }));
}
main().catch(error => { console.error(error); process.exitCode = 1; });
