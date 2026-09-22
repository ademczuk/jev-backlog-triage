/**
 * Backlog triage over Vercel AI Gateway using TypeSafe AI's jev.
 *
 * WHY THIS SHAPE. jev is a decision model, not a generator: it takes a `state`
 * and typed `questions` and returns a probability distribution per question,
 * plus a calibrated confidence. It cannot write text, invent options, or reason
 * in steps. So every judgment here is expressed as a closed question with the
 * options enumerated up front, and anything jev is unsure about is escalated
 * rather than guessed.
 *
 * THE CONFIDENCE IS THE PRODUCT, NOT THE LABEL. A classifier that returns a
 * label forces you to trust every row equally. This returns a band, so cheap
 * certain rows clear automatically and the genuinely ambiguous ones surface as
 * a short human queue. That is the only reason this is worth running over a
 * backlog rather than reading it.
 *
 * WHAT "CANNOT HALLUCINATE" ACTUALLY MEANS. It means jev cannot break the
 * schema: it will never return a field you did not define or an option you did
 * not list. It does NOT mean the answer is right. A confidently wrong answer is
 * still wrong, which is why ESCALATE_BELOW is a policy knob and not a constant.
 *
 * Auth: `vercel link && vercel env pull` puts AI_GATEWAY_API_KEY in .env.local.
 * Deployments get the token automatically; a local token expires after 12h.
 */
import { experimental_evaluate as evaluate } from 'ai';
import { readFileSync } from 'node:fs';

/** Below this confidence a row goes to a human instead of being actioned. */
const ESCALATE_BELOW = 0.7;

/** jev caps `state` at 32k tokens, so long rows must be trimmed, not truncated mid-word. */
const MAX_STATE_CHARS = 24_000;

type Item = { id: string; text: string; in_board: boolean };

const questions = {
  owner: {
    type: 'choice' as const,
    instructions: 'Who must act next to move this item forward? Choose by who does the work, not who is accountable for the outcome.',
    criteria: {
      engineer: 'An engineer must build, investigate, or decide something technical.',
      sponsor: 'The client sponsor must answer, approve, or supply a business fact.',
      joint: 'Genuinely needs both in the same conversation.',
      unassigned: 'Nobody can act until something else resolves first.',
    },
  },
  blocks_milestone: {
    type: 'boolean' as const,
    instructions: 'Does the first milestone fail to ship if this item is still open at its ceiling?',
    criteria: {
      true: 'The milestone cannot be accepted while this is open.',
      false: 'The milestone can ship with this still open.',
    },
  },
  size_class: {
    type: 'score' as const,
    instructions: 'How much agent working time would one competent pass at this take? This is the sampling frame for measuring session-hours per ticket, so judge effort, not importance.',
    criteria: [
      'Under an hour. Single file or a one-line decision.',
      'Half a day. One component, no unknowns.',
      'Two days. Several components or a small unknown.',
      'A week. Cross-cutting, or a real unknown to resolve first.',
      'More than a week, or cannot be sized without spiking it.',
    ],
  },
} as const;

async function triage(item: Item) {
  const state = item.text.slice(0, MAX_STATE_CHARS);
  const result = await evaluate({
    model: 'typesafe-ai/jev',
    state,
    questions,
    // Client material must not be retained by the gateway. Per-request ZDR is
    // a Pro and Enterprise feature on Vercel; on a Hobby team the gateway
    // refuses it. So it is on unless explicitly disabled, and disabling it
    // is a loud env var rather than a quiet default, because that is the
    // direction the mistake must be hard in.
    providerOptions: { gateway: { zeroDataRetention: process.env.JEV_ALLOW_RETENTION !== '1' } },
  });

  const conf = { ...((result.providerMetadata?.typesafe?.confidence ?? {}) as Record<string, number>) };
  // The gateway reports confidence for choice and score questions only. A
  // boolean has no entry because its probability already is the confidence:
  // 0.5 is a coin flip, 0 or 1 is certainty. Map it onto the same 0..1 scale
  // rather than reading the missing key as zero, which escalated every row.
  const b = result.answers.blocks_milestone?.probability;
  if (typeof b === 'number') conf.blocks_milestone = Math.abs(b - 0.5) * 2;
  const weakest = Math.min(...Object.keys(questions).map((k) => conf[k] ?? 0));

  return {
    id: item.id,
    owner: result.answers.owner,
    blocks_milestone: result.answers.blocks_milestone,
    size_class: result.answers.size_class,
    confidence: conf,
    weakest_confidence: weakest,
    // Two independent reasons a row needs a human: jev was unsure, or the
    // record and the board disagree about whether it is even tracked.
    needs_human: weakest < ESCALATE_BELOW,
    untracked_but_blocking: !item.in_board && result.answers.blocks_milestone?.probability > 0.5,
  };
}

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
