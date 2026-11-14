// A45 / P37 gate harness: runs the kit's command with pinned files in place of the network.
// usage: node arena_kit_harness.mjs <kit.mjs URL> <spec.json>
// spec: { files: {feed, door, board}, mutate?: "feed"|"door"|"board"|"down", argv: [...] }
import { readFileSync } from 'node:fs';

const [, , kitUrl, specPath] = process.argv;
const spec = JSON.parse(readFileSync(specPath, 'utf8'));
const kit = await import(kitUrl);
const byUrl = { [kit.ENDPOINTS.feed]: 'feed', [kit.ENDPOINTS.door]: 'door', [kit.ENDPOINTS.board]: 'board' };
const out = []; const writes = {}; const gets = [];
const io = {
  get: async (url) => {
    gets.push(url);
    const name = byUrl[url];
    if (!name) throw new Error('a GET outside the three endpoints');
    if (spec.mutate === 'down') throw new Error('HTTP 503');
    let text = readFileSync(spec.files[name], 'utf8');
    if (spec.mutate === name) text = text.replace(kit.SETTLED_SHA256, 'd' + kit.SETTLED_SHA256.slice(1));
    return text;
  },
  write: (path, text) => { writes[path] = text; },
  out: (line) => out.push(line),
};
const code = await kit.run(spec.argv, io);
process.stdout.write(JSON.stringify({ code, out, writes, gets }));
