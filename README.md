# AIWave Quickstart

Call Chinese AI models through one OpenAI-compatible endpoint — **97 public routes, 10 Chinese families, 13 public video routes.** Keep your client code stable while you choose the model for the job.

[![Models](https://img.shields.io/badge/public%20rate%20card-97%20routes-blue)](https://aiwave.live/models)
[![Video](https://img.shields.io/badge/public%20video%20routes-13-purple)](https://aiwave.live/models)
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

## 6. Prompt library sample

**[aiwave-video-pack](https://github.com/AIWaveAPI/aiwave-video-pack)** —
four bilingual video-prompt modules (three cinematic styles + one camera
move), each with a validation record and a reproduction command. Free (CC
BY-NC). Works with any video model.

## 7. Handle the common responses

- `401`: check that the key is present and the `Bearer` prefix is included.
- `402`: add balance or use an enabled account group with available quota.
- `404`: model ID not found or retired — copy the exact ID from [aiwave.live/models](https://aiwave.live/models).
- `429`: retry with bounded exponential backoff and avoid an unbounded loop.
- `5xx`: keep the request id, retry only when the operation is safe to repeat,
  and check the service status page.

## 8. Estimate your cost

Before you build, know what the workload will cost. `scripts/cost.py` reads the
same live endpoint as the pricing page — no API key needed.

```bash
# One model, your own numbers
python3 scripts/cost.py --model deepseek-v4-flash --messages 500 \
  --avg-input 2000 --avg-output 500

# Compare several models on a preset workload (chat / agent)
python3 scripts/cost.py --compare glm-5,kimi-k3,deepseek-v4-pro --preset agent

# Video routes are billed per clip
python3 scripts/cost.py --preset video --model kling-v2-6 --clips 30
```

Every run prints the fetch time and the pricing version, so results are
reproducible. Misspelled model IDs get a suggestion from the live catalog.

## 9. Contributing & support

Found a wrong price? That's the most useful contribution you can make — see
[CONTRIBUTING.md](CONTRIBUTING.md). For other questions, use
[Discussions](https://github.com/AIWaveAPI/aiwave-quickstart/discussions) or
open a structured [issue](https://github.com/AIWaveAPI/aiwave-quickstart/issues/new/choose).

Security issues: **do not open a public issue** — see [SECURITY.md](SECURITY.md).

## Repository layout

- `examples/curl.sh` — minimal shell request
- `examples/python.py` — OpenAI Python client
- `examples/node.mjs` — OpenAI Node client
- `examples/video_curl.sh` — AI video generation + polling (curl)
- `examples/video_python.py` — video generation (submit → poll → URL)
- `examples/video_node.mjs` — same flow in Node.js
- `.env.example` — local variable names only
- `scripts/cost.py` — estimate cost from live prices

This repository contains examples, not credentials. Replace the model ID with
one that fits your workload and verify current pricing before production use.
