#!/usr/bin/env node
/**
 * AIWave video generation example: submit a job, poll until done, print the URL.
 *
 * Video routes are experimental and require a paid account group (from $5).
 * Battle-tested notes (from real productions, 2026-10):
 *   - A single shot takes 5-11 minutes. Poll every 15s; give up after 15 min.
 *   - Some upstream channels stall without a reference image. If a task
 *     stays NOT_START with 0% progress for >3 minutes, keep its task ID and
 *     check status or usage before submitting another billable job.
 *
 * Usage:
 *   export AIWAVE_API_KEY="sk-..."   # https://aiwave.live/register
 *   node examples/video_node.mjs "A red sports car drifting through a neon city"
 */

const BASE_URL = process.env.AIWAVE_BASE_URL || "https://aiwave.live/v1";
const MODEL = process.env.AIWAVE_VIDEO_MODEL || "kling-v2-6";
const API_KEY = process.env.AIWAVE_API_KEY || "";

const prompt =
  process.argv[2] ||
  "A red sports car drifting through a neon-lit city at night, cinematic tracking shot, rain reflections";

if (!API_KEY) {
  console.error("Set AIWAVE_API_KEY first (https://aiwave.live/register)");
  process.exit(1);
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function call(path, body) {
  const res = await fetch(`${BASE_URL}${path}`, {
    method: body ? "POST" : "GET",
    headers: {
      Authorization: `Bearer ${API_KEY}`,
      "Content-Type": "application/json",
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  return res.json();
}

async function main() {
  console.log(`==> Submitting video job (${MODEL})...`);
  const submitted = await call("/video/generations", { model: MODEL, prompt });
  const taskId = submitted.task_id || submitted.id;
  if (!taskId) {
    console.error("No task_id in response:", JSON.stringify(submitted).slice(0, 300));
    process.exit(1);
  }
  console.log(`    task_id: ${taskId}`);

  let notStartSince = null;
  for (let i = 1; i <= 60; i++) {
    await sleep(15000);
    const status = await call(`/video/generations/${taskId}`);
    const data = status.data || status;
    const st = data.status || "?";
    const prog = data.progress || "";
    console.log(`  [${i * 15}s] ${st} ${prog}`);

    if (st === "SUCCESS") {
      const m = JSON.stringify(status).match(/https?:\/\/[^"\\]+\.mp4[^"\\]*/);
      console.log(`\nDone: ${m ? m[0] : "(scan response for URL)"}`);
      return;
    }
    if (st === "FAILURE") {
      console.error(`Failed upstream: ${data.fail_reason || "unknown"}`);
      process.exit(1);
    }

    // Silent-failure heuristic: stuck at 0% for >3 minutes
    const stuck = (st === "NOT_START" || st === "QUEUING") && (!prog || prog === "0%" || prog === 0);
    if (stuck) {
      notStartSince = notStartSince || Date.now();
      if (Date.now() - notStartSince > 180000) {
        console.error(
          "Stuck >3 min with 0% progress. Keep the task ID and check status or usage before submitting another job."
        );
        process.exit(1);
      }
    } else {
      notStartSince = null;
    }
  }
  console.error("Timed out after 15 minutes");
  process.exit(1);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
