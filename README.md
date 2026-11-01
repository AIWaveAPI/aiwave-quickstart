# AIWave Quickstart

Call Chinese AI models through one OpenAI-compatible endpoint — **97 public routes, 10 Chinese families, 10 public video routes.** Keep your client code stable while you choose the model for the job.

[![Models](https://img.shields.io/badge/public%20rate%20card-97%20routes-blue)](https://aiwave.live/models)
[![Video](https://img.shields.io/badge/public%20video%20routes-10-purple)](https://aiwave.live/models)
[![Docs](https://img.shields.io/badge/docs-quickstart-blue)](https://aiwave.live/docs/quickstart)

## 1. Set your environment

Create a key in the [AIWave console](https://aiwave.live/register), then export it locally:

```bash
export AIWAVE_API_KEY="your_api_key"
export AIWAVE_BASE_URL="https://aiwave.live/v1"
export AIWAVE_MODEL="deepseek-v4-flash"
```

The key belongs in your environment or secret manager. Do not commit it.

## 2. Make the first request

### curl

```bash
curl "$AIWAVE_BASE_URL/chat/completions" \
  -H "Authorization: Bearer $AIWAVE_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{\"model\":\"$AIWAVE_MODEL\",\"messages\":[{\"role\":\"user\",\"content\":\"Say hello in one sentence.\"}],\"max_tokens\":64}"
```

### Python

```bash
python -m pip install openai
python examples/python.py
```

### Node.js

```bash
npm install openai
node examples/node.mjs
```

## 3. Choose a model

Use the public model list at [aiwave.live/models](https://aiwave.live/models)
and the dated rate card at [aiwave.live/pricing](https://aiwave.live/pricing).
Model IDs are explicit, so you can change the model without changing the
request shape.

Popular picks (reasoning & chat):

| Model | Best for | Rate |
|---|---|---|
| `deepseek-v4-flash` | Fast, cheap reasoning | $0.30 / $1.20 per 1M |
| `deepseek-v4-pro` | Flagship reasoning | $1.32 / $3.96 per 1M |
| `glm-5` | Balanced general use | $1.55 / $4.96 per 1M |
| `kimi-k3` | Long-context workloads | see [pricing](https://aiwave.live/pricing) |
| `qwen3.8-max` | Qwen flagship | see [pricing](https://aiwave.live/pricing) |

## 5. AI video (experimental)

> **Status: experimental.** The video endpoint occasionally surfaces upstream
> channel errors while we harden it. Try it, but don't build production
> workflows on it yet. A much better experience — a full cinematic prompt
> system and storyboard engine — is coming with **AIWave Canvas** (see below).

The same key also drives AI video routes — Kling, Seedance, Hailuo, Wan, and
Vidu. Video routes require a paid account group (from $5).

```bash
bash examples/video_curl.sh "A red sports car drifting through a neon city"
```

Full list of video models: [aiwave.live/models](https://aiwave.live/models).

## 6. Coming soon: AIWave Canvas

We're building **AIWave Canvas** — a cinematic creation platform on top of
these routes:

- A professional prompt library (styles, camera moves, micro-expressions,
  pacing — battle-tested on real productions, not generated filler)
- A storyboard engine that assembles shots automatically and keeps characters
  consistent across scenes
- One flow from script → storyboard → rendered video

**Free sample from the prompt library is already open** — see
[aiwave-video-pack](https://github.com/AIWaveAPI/aiwave-video-pack) for three
battle-tested cinematic style prompts you can use today with any video model.

Follow the org or star the repos — Canvas launches here first.

## 7. Handle the common responses

- `401`: check that the key is present and the `Bearer` prefix is included.
- `402`: add balance or use an enabled account group with available quota.
- `404`: model ID not found or retired — copy the exact ID from [aiwave.live/models](https://aiwave.live/models).
- `429`: retry with bounded exponential backoff and avoid an unbounded loop.
- `5xx`: keep the request id, retry only when the operation is safe to repeat,
  and check the service status page.

## Repository layout

- `examples/curl.sh` — minimal shell request
- `examples/python.py` — OpenAI Python client
- `examples/node.mjs` — OpenAI Node client
- `examples/video_curl.sh` — AI video generation + polling
- `.env.example` — local variable names only

This repository contains examples, not credentials. Replace the model ID with
one that fits your workload and verify current pricing before production use.
