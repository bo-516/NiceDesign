#!/usr/bin/env node
/* Fallback for build.py when python3 is missing: embeds a plan JSON in template.html
   the same way build.py does, but checks nothing. Open the result: the page lists
   the problems it can detect at the top.

       node embed.mjs docs/plan.json                 # writes docs/plan.html next to it
       node embed.mjs docs/plan.json -o out.html
*/
import { readFileSync, writeFileSync } from 'node:fs';

const MARKER = '<script type="application/json" id="doc-data">null</script>';
const [src, flag, dest, ...extra] = process.argv.slice(2);
if (!src || (flag && (flag !== '-o' || !dest)) || extra.length) {
  console.error('usage: node embed.mjs docs/plan.json [-o out.html]');
  process.exit(2);
}

let doc;
try {
  doc = JSON.parse(readFileSync(src, 'utf8'));
} catch (e) {
  console.error(`✗ ${src}: ${e.message}`);
  process.exit(1);
}
const template = readFileSync(new URL('template.html', import.meta.url), 'utf8');
if (template.split(MARKER).length !== 2) {
  console.error('✗ template.html: data marker not found exactly once');
  process.exit(1);
}

const esc = s => String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
// Inside <script>, only "</" can end the block early; \u003c parses back to the same JSON.
const payload = JSON.stringify(doc, null, 2).replace(/</g, '\\u003c');
const html = template
  .replace(MARKER, () => `<script type="application/json" id="doc-data">\n${payload}\n</script>`)
  .replace(/<title>.*?<\/title>/, () => `<title>${esc(doc?.title ?? '')}</title>`)
  .replace(/<html lang="[^"]*">/, () => `<html lang="${esc(doc?.lang ?? 'zh-CN')}">`);

const out = dest ?? src.replace(/\.json$/i, '') + '.html';
writeFileSync(out, html);
console.log(`✓ ${out} (not checked: open it and fix any problems listed at the top)`);
