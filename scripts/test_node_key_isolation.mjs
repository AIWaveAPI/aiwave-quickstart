import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { copyFileSync, mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const source = join(dirname(fileURLToPath(import.meta.url)), "..", "examples", "node.mjs");
const root = mkdtempSync(join(tmpdir(), "aiwave-node-key-"));
try {
  const packageDir = join(root, "node_modules", "openai");
  mkdirSync(packageDir, { recursive: true });
  writeFileSync(join(packageDir, "package.json"), JSON.stringify({ name: "openai", type: "module", exports: "./index.mjs" }));
  writeFileSync(join(packageDir, "index.mjs"), `
export default class OpenAI {
  constructor(options) {
    const key = options.apiKey ?? process.env.OPENAI_API_KEY;
    process.stdout.write("used-key:" + key + "\\n");
    this.chat = { completions: { create: async () => ({ choices: [{ message: { content: "hello" } }] }) } };
  }
}
`);
  const example = join(root, "node.mjs");
  copyFileSync(source, example);
  const env = { ...process.env, OPENAI_API_KEY: "ambient-test-only" };
  delete env.AIWAVE_API_KEY;
  const missing = spawnSync(process.execPath, [example], { env, encoding: "utf8" });
  assert.equal(missing.status, 2, missing.stderr);
  assert.match(missing.stderr, /AIWAVE_API_KEY/);
  assert.doesNotMatch(missing.stdout + missing.stderr, /ambient-test-only/);

  const own = spawnSync(process.execPath, [example], {
    env: { ...env, AIWAVE_API_KEY: "own-test-key" }, encoding: "utf8",
  });
  assert.equal(own.status, 0, own.stderr);
  assert.match(own.stdout, /used-key:own-test-key/);
  assert.match(own.stdout, /hello/);
  assert.doesNotMatch(own.stdout + own.stderr, /ambient-test-only/);
  console.log("Node quickstart key isolation: PASS");
} finally {
  rmSync(root, { recursive: true, force: true });
}
