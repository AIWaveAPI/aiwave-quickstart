#!/usr/bin/env node
/** Offline checks for the copy-paste Node error handler. */
import assert from 'node:assert/strict';
import { chatWithRetries, handle, retryAfterSeconds } from '../examples/error_handling.mjs';

assert.equal(await handle(503, '{}', { requestId: 'test' }), false);
assert.equal(retryAfterSeconds(new Headers({ 'Retry-After': '120' }), 0), 120);
const deadline = new Date(Date.now() + 120_000).toUTCString();
const dateWait = retryAfterSeconds(new Headers({ 'Retry-After': deadline }), 0);
assert.ok(dateWait > 90 && dateWait <= 120, 'HTTP-date Retry-After is honored');

const originalFetch = globalThis.fetch;
let calls = 0;
try {
  globalThis.fetch = async () => {
    calls += 1;
    return {
      ok: false,
      status: 503,
      headers: new Headers(),
      text: async () => '{"error":{"message":"upstream"}}',
    };
  };
  await assert.rejects(
    chatWithRetries('test-model', [{ role: 'user', content: 'hi' }],
                    { apiKey: 'test-only', maxRetries: 3 }),
    /HTTP 503/,
  );
  assert.equal(calls, 1, '5xx must not send a second billable request');

  calls = 0;
  globalThis.fetch = async () => {
    calls += 1;
    return {
      ok: false,
      status: 429,
      headers: new Headers({ 'Retry-After': '120' }),
      text: async () => '{}',
    };
  };
  await assert.rejects(
    chatWithRetries('test-model', [{ role: 'user', content: 'hi' }],
                    { apiKey: 'test-only', maxRetries: 3 }),
    /retry after 120s/,
  );
  assert.equal(calls, 1, 'long Retry-After must not retry early');
} finally {
  globalThis.fetch = originalFetch;
}

console.log('All Node error-handler checks passed.');
