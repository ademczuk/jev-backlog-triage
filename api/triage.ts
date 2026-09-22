/**
 * The one place the gateway key lives. The static frontend on GitHub Pages
 * cannot hold a secret, so it posts rows here and this function makes the
 * jev call with AI_GATEWAY_API_KEY from the Vercel environment.
 */
import { triage, type Item } from '../src/lib.ts';

const ALLOW = /^https:\/\/ademczuk\.github\.io$|^http:\/\/localhost(:\d+)?$/;

export default async function handler(req: any, res: any) {
  const origin = req.headers.origin ?? '';
  if (ALLOW.test(origin)) res.setHeader('Access-Control-Allow-Origin', origin);
  res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
  if (req.method === 'OPTIONS') return res.status(204).end();
  if (req.method !== 'POST') return res.status(405).json({ error: 'POST a JSON array of {id, text, in_board}' });

  const items: Item[] = Array.isArray(req.body) ? req.body : req.body?.items;
  if (!Array.isArray(items) || items.length === 0 || items.length > 50) {
    return res.status(400).json({ error: 'body must be 1 to 50 items' });
  }
  try {
    const rows = [];
    for (const it of items) rows.push(await triage({ id: String(it.id), text: String(it.text).slice(0, 24_000), in_board: !!it.in_board }));
    return res.status(200).json({ rows });
  } catch (err: any) {
    const gw = err?.cause?.data?.error ?? err?.data?.error;
    return res.status(502).json({ error: gw?.message ?? err?.message ?? 'jev call failed' });
  }
}
