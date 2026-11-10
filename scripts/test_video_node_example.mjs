import test from 'node:test';
import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import { spawn } from 'node:child_process';

test('missing task ID keeps response private and submits once', async () => {
  const requests = [];
  const server = createServer((request, response) => {
    requests.push([request.method, request.url]);
    response.writeHead(200, { 'content-type': 'application/json' });
    response.end(JSON.stringify({ data: {
      status: 'IN_PROGRESS', private_detail: 'synthetic-private-marker',
    } }));
  });
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  try {
    const { port } = server.address();
    const child = spawn(process.execPath, ['examples/video_node.mjs', 'synthetic prompt'], {
      env: { ...process.env, AIWAVE_API_KEY: 'synthetic-only',
        AIWAVE_BASE_URL: `http://127.0.0.1:${port}/v1` },
    });
    let output = '';
    child.stdout.on('data', (chunk) => { output += chunk; });
    child.stderr.on('data', (chunk) => { output += chunk; });
    const exitCode = await new Promise((resolve, reject) => {
      child.on('error', reject);
      child.on('exit', resolve);
      setTimeout(() => { child.kill(); reject(new Error('example timed out')); }, 10000).unref();
    });
    assert.notEqual(exitCode, 0);
    assert.deepEqual(requests, [['POST', '/v1/video/generations']]);
    assert.match(output, /Check task history and usage/);
    assert.doesNotMatch(output, /synthetic-private-marker/);
  } finally {
    await new Promise((resolve) => server.close(resolve));
  }
});

test('polling keeps an opaque task ID inside one URL path segment', async () => {
  const requests = [];
  const server = createServer((request, response) => {
    requests.push([request.method, request.url]);
    response.writeHead(200, { 'content-type': 'application/json' });
    response.end(JSON.stringify(request.method === 'POST'
      ? { data: { task_id: 'job/part?mode=unsafe#fragment', status: 'IN_PROGRESS' } }
      : { data: { status: 'SUCCESS', progress: '100%' } }));
  });
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  try {
    const { port } = server.address();
    const child = spawn(process.execPath, ['examples/video_node.mjs', 'synthetic prompt'], {
      env: { ...process.env, AIWAVE_API_KEY: 'synthetic-only',
        AIWAVE_BASE_URL: `http://127.0.0.1:${port}/v1` },
    });
    const exitCode = await new Promise((resolve, reject) => {
      child.on('error', reject);
      child.on('exit', resolve);
      setTimeout(() => { child.kill(); reject(new Error('example timed out')); }, 20000).unref();
    });
    assert.equal(exitCode, 0);
    assert.deepEqual(requests, [
      ['POST', '/v1/video/generations'],
      ['GET', '/v1/video/generations/job%2Fpart%3Fmode%3Dunsafe%23fragment'],
    ]);
  } finally {
    await new Promise((resolve) => server.close(resolve));
  }
});
