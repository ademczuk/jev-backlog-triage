/**
 * Calibration run: public, human-labelled data through typesafe-ai/jev, every item twice.
 * Usage: node --env-file-if-exists=.env.local --experimental-strip-types research/calibrate.ts <set> <pass>
 * Writes research/results/<set>.<pass>.jsonl, one line per item, errors included, never dropped.
 */
import { readFileSync, appendFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { experimental_evaluate as evaluate } from 'ai';

const [set, pass] = process.argv.slice(2);
if (!set || !pass) throw new Error('usage: calibrate.ts <sst2|irony|banking77> <pass>');
const CONCURRENCY = Number(process.env.JEV_CONCURRENCY ?? 8);

const dir = new URL('.', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1');
const items = readFileSync(`${dir}data/${set}.jsonl`, 'utf8').trim().split('\n').map((l) => JSON.parse(l))
  .slice(Number(process.env.JEV_OFFSET ?? 0), Number(process.env.JEV_OFFSET ?? 0) + Number(process.env.JEV_LIMIT ?? 1e9))
  .filter((it: any) => !process.env.JEV_ONLY_IDS || process.env.JEV_ONLY_IDS.split(',').includes(it.id));

function questionsFor(s: string) {
  if (s === 'sst2') {
    return {
      q: {
        type: 'boolean' as const,
        instructions: 'Is the sentiment of this sentence from a movie review positive?',
        criteria: { true: 'The sentence expresses positive sentiment.', false: 'The sentence expresses negative sentiment.' },
      },
    };
  }
  if (s === 'irony') {
    return {
      q: {
        type: 'boolean' as const,
        instructions: 'Is this tweet ironic?',
        criteria: { true: 'The tweet is ironic or sarcastic.', false: 'The tweet is meant literally.' },
      },
    };
  }
  if (s === 'telco' || s === 'telco_hostile') {
    return {
      q: {
        type: 'boolean' as const,
        instructions: 'This is a telecom customer record. Will this customer churn (leave the company)?',
        criteria: { true: 'The customer churns.', false: 'The customer stays.' },
      },
    };
  }
  if (s === 'bank') {
    return {
      q: {
        type: 'boolean' as const,
        instructions: 'This is a record of a bank client contacted in a phone marketing campaign. Did the client subscribe to a term deposit?',
        criteria: { true: 'The client subscribed.', false: 'The client did not subscribe.' },
      },
    };
  }
  if (s === 'routing') {
    return {
      q: {
        type: 'boolean' as const,
        instructions: 'Could a small, inexpensive language model answer this question correctly?',
        criteria: { true: 'A small model would get this right.', false: 'This needs a strong model.' },
      },
    };
  }
  if (s === 'injection') {
    return {
      q: {
        type: 'boolean' as const,
        instructions: 'Does this text try to override, redirect or manipulate the instructions given to an AI system?',
        criteria: { true: 'It tries to change what the AI was told to do.', false: 'It is an ordinary request or statement.' },
      },
    };
  }
  if (s === 'tools') {
    const tools: Record<string, string> = JSON.parse(readFileSync(`${dir}data/tools.options.json`, 'utf8'));
    return {
      q: {
        type: 'choice' as const,
        instructions: 'Which tool should an assistant use to handle this request?',
        criteria: tools,
      },
    };
  }
  if (s === 'banking77') {
    const labels: string[] = JSON.parse(readFileSync(`${dir}data/banking77.labels.json`, 'utf8'));
    return {
      q: {
        type: 'choice' as const,
        instructions: 'Which intent best describes this message from a bank customer?',
        criteria: Object.fromEntries(labels.map((l) => [l, l.replace(/_/g, ' ')])),
      },
    };
  }
  throw new Error(`unknown set ${s}`);
}
const questions = questionsFor(set);

async function one(item: any) {
  const t0 = performance.now();
  try {
    const r: any = await evaluate({
      model: 'typesafe-ai/jev',
      state: item.text,
      questions,
      maxRetries: 1,
      abortSignal: AbortSignal.timeout(Number(process.env.JEV_TIMEOUT_MS ?? 30000)),
      providerOptions: { gateway: { zeroDataRetention: true } },
    });
    return {
      id: item.id,
      label: item.label,
      answer: r.answers.q,
      confidence: r.providerMetadata?.typesafe?.confidence?.q ?? null,
      rounding: r.rounding ?? null,
      usage: r.usage,
      ms: Math.round(performance.now() - t0),
    };
  } catch (err: any) {
    const gw = err?.cause?.data?.error ?? err?.data?.error;
    return { id: item.id, label: item.label, error: gw?.message ?? String(err?.message ?? err), ms: Math.round(performance.now() - t0) };
  }
}

mkdirSync(`${dir}results`, { recursive: true });
const file = `${dir}results/${set}.${pass}.jsonl`;
writeFileSync(file, '');
const out: any[] = [];
let next = 0;
const started = performance.now();
await Promise.all(
  Array.from({ length: CONCURRENCY }, async () => {
    while (next < items.length) {
      const i = next++;
      const r = await one(items[i]);
      out.push(r);
      appendFileSync(file, JSON.stringify(r) + '\n');
      if (out.length % 50 === 0) {
        const e = out.filter((x) => x.error).length;
        console.error(`[${set}.${pass}] ${out.length}/${items.length} done, ${e} errors, ${Math.round((performance.now() - started) / 1000)}s`);
      }
    }
  }),
);
const errors = out.filter((r) => r.error).length;
console.log(`${set} pass ${pass}: ${out.length} rows, ${errors} errors, written ${file}`);
if (errors) console.log('first error:', out.find((r) => r.error).error);
