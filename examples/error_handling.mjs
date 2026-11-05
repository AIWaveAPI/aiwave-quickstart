#!/usr/bin/env node
/**
 * Copy-paste error handling for AIWave / OpenAI-compatible clients.
 * Node 18+ (uses built-in fetch). No dependencies.
 *
 * Usage:
 *   AIWAVE_API_KEY=sk-... node examples/error_handling.mjs
 */

const BASE_URL = process.env.AIWAVE_BASE_URL || 'https://aiwave.live/v1';
const PRICING = 'https://aiwave.live/api/pricing';
const MAX_AUTO_WAIT_SECONDS = 60;

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function closest(name, ids) {
  // small edit-distance suggestion without a dependency
  const dist = (a, b) => {
    const dp = Array.from({ length: a.length + 1 }, (_, i) => [i, ...Array(b.length).fill(0)]);
    for (let j = 0; j <= b.length; j++) dp[0][j] = j;
    for (let i = 1; i <= a.length; i++)
      for (let j = 1; j <= b.length; j++)
        dp[i][j] = Math.min(dp[i - 1][j] + 1, dp[i][j - 1] + 1,
                            dp[i - 1][j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1));
    return dp[a.length][b.length];
  };
  return ids
    .map((id) => [id, dist(name.toLowerCase(), id.toLowerCase())])
    .sort((a, b) => a[1] - b[1])
    .slice(0, 3)
    .map(([id]) => id);
}

async function liveModelIds() {
  try {
    const r = await fetch(PRICING, { signal: AbortSignal.timeout(15000) });
    const d = await r.json();
    const ms = d.models || d.data || [];
    return ms.map((m) => m.model_name || m.id);
  } catch {
    return [];
  }
}

/** Print a concrete next action. Returns true if the request is retryable. */
export async function handle(status, body, { requestId, model } = {}) {
  if (status === 401) {
    console.log('401 �� authentication failed.');
    console.log("  Check: AIWAVE_API_KEY is set, starts with 'sk-', and the header is");
    console.log("  'Authorization: Bearer <key>' (the word Bearer is required).");
    return false;
  }
  if (status === 402) {
    console.log('402 �� insufficient balance or no enabled group with quota.');
    console.log('  Add balance at https://aiwave.live/pricing. Not retryable.');
    return false;
  }
  if (status === 404) {
    console.log('404 �� model ID not found or retired.');
    console.log('  Copy the exact ID from https://aiwave.live/models');
    const ids = await liveModelIds();
    if (model && ids.length) {
      const near = closest(model, ids);
      if (near.length) console.log(`  Closest currently on the rate card: ${near.join(', ')}`);
    }
    return false;
  }
  if (status === 429) {
    console.log('429 �� rate limited. Retry with bounded exponential backoff + jitter.');
    console.log("  Prefer the server's Retry-After header over local backoff.");
    return true;
  }
  if (status >= 500 && status < 600) {
    console.log(`${status} �� upstream/server error. Request id: ${requestId || '(none)'}`);
    console.log('  The upstream may have completed this request. Check usage and keep');
    console.log('  the request id before deciding whether to submit another request.');
    return false;
  }
  console.log(`${status} �� unhandled status: ${String(body).slice(0, 200)}`);
  return false;
}

/** Retry-After wins; otherwise exponential backoff + jitter, capped at 30s. */
export function retryAfterSeconds(headers, attempt) {
  const raw = headers?.get?.('Retry-After');
  if (raw) {
    const n = Number(raw);
    if (Number.isFinite(n) && n >= 0) return n;
    const deadline = Date.parse(raw);
    if (Number.isFinite(deadline)) return Math.max(0, (deadline - Date.now()) / 1000);
  }
  return Math.min(2 ** attempt + Math.random() * 0.5, 30);
}

/** A complete request with bounded 429 retries. Never auto-retry 5xx. */
export async function chatWithRetries(model, messages, { apiKey, maxRetries = 3 } = {}) {
  const key = apiKey || process.env.AIWAVE_API_KEY;
  if (!key) throw new Error('Set AIWAVE_API_KEY first (https://aiwave.live/register)');

  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    const res = await fetch(`${BASE_URL}/chat/completions`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${key}`, 'Content-Type': 'application/json' },
      body: JSON.stringify({ model, messages }),
      signal: AbortSignal.timeout(60000),
    });
    if (res.ok) return res.json();

    const body = await res.text();
    const requestId = res.headers.get('x-request-id');
    const retryable = await handle(res.status, body, { requestId, model });
    if (!retryable || attempt === maxRetries) {
      throw new Error(`HTTP ${res.status}: ${body.slice(0, 200)}`);
    }
    const wait = retryAfterSeconds(res.headers, attempt);
    if (wait > MAX_AUTO_WAIT_SECONDS) {
      console.log(`  Retry-After is ${Math.ceil(wait)}s; stop automatic retries and try later.`);
      throw new Error(`HTTP ${res.status}: retry after ${Math.ceil(wait)}s`);
    }
    console.log(`  retrying in ${wait.toFixed(1)}s (attempt ${attempt + 1}/${maxRetries})`);
    await sleep(wait * 1000);
  }
}

if (import.meta.url === `file://${process.argv[1]}`) {
  console.log('=== Real 401 smoke test (bad key) ===');
  try {
    await chatWithRetries('deepseek-v4-flash',
      [{ role: 'user', content: 'hi' }],
      { apiKey: 'sk-invalid-for-smoke-test', maxRetries: 0 });
  } catch (e) {
    console.log(`  ${e.message.slice(0, 80)} �� handler printed the checklist above.`);
  }
}
