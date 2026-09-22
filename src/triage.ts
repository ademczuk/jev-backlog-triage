import { readFileSync } from 'node:fs';
import { triage, type Item } from './lib.ts';

const items: Item[] = JSON.parse(readFileSync(process.argv[2] ?? 'data/items.sample.json', 'utf8'));
const rows = [];
try {
  for (const item of items) rows.push(await triage(item));
} catch (err: any) {
  // The gateway explains itself in one sentence; the SDK wraps that in a
  // hundred lines of request echo. Surface the sentence, keep the exit code.
  const gw = err?.cause?.data?.error ?? err?.data?.error;
  if (gw?.message) {
    console.error(`gateway refused (${err?.cause?.statusCode ?? err?.statusCode ?? '?'} ${gw.type ?? ''}): ${gw.message}`);
    process.exit(2);
  }
  throw err;
}

const auto = rows.filter((r) => !r.needs_human).length;
const gap = rows.filter((r) => r.untracked_but_blocking);

console.log(JSON.stringify(rows, null, 2));
console.log(`\n${rows.length} items, ${auto} cleared automatically, ${rows.length - auto} to a human.`);
if (gap.length) {
  console.log(`${gap.length} are MILESTONE-BLOCKING AND NOT ON THE BOARD: ${gap.map((r) => r.id).join(', ')}`);
}
