# AIWave Quickstart

Call Chinese AI models through one OpenAI-compatible endpoint — **97 public routes, 10 Chinese families, 13 public video routes.** Keep your client code stable while you choose the model for the job.

[![Models](https://img.shields.io/badge/public%20rate%20card-97%20routes-blue)](https://aiwave.live/models)
[![Video](https://img.shields.io/badge/public%20video%20routes-13-purple)](https://aiwave.live/models)
[![Docs](https://img.shields.io/badge/docs-quickstart-blue)](https://aiwave.live/docs/quickstart)

## 0. Which model ID should I use?

Model IDs are exact and case-sensitive. Vendors retire them without notice, so
confirm against the live public rate card instead of copying an ID from an old
blog post:

```bash
curl -s https://aiwave.live/api/pricing | python3 -c \
  "import sys,json; d=json.load(sys.stdin); ms=d['models'] if 'models' in d else d['data']; print('\n'.join(m['model_name'] for m in ms))"
```

Common searches and the exact IDs on our card (a lookup table, not a review):

| Searching for | Exact IDs currently on the card |
|---|---|
| `deepseek v4 flash` / `deepseek flash` | `deepseek-v4-flash`, `deepseek-flash`, `deepseek-v4.1-flash` |
| `deepseek v4 pro` | `deepseek-v4-pro` |
| `qwen3 coder` / Qwen coding | `qwen3.8-max`, `qwen3.8-27b`; coding-specific: `kimi-k2.7-code`, `kimi-k2.7-code-highspeed`. There is no `qwen3-coder` ID on our card. |
| `kimi k3` | `kimi-k3`, `kimi-k2.6` |
| `chinese embedding models` | `qwen3.7-text-embedding` |
| `kling` / `seedance` / `wan` video | `kling-v3`, `kling-video-o1`, `doubao-seedance-2-5-260628`, `wan3.0-video` |
| `chinese ai api pricing 2026` | [Dated USD rates](https://aiwave.live/pricing) · `python3 scripts/cost.py --compare <ids>` |

Every number in this repo is checked against that endpoint by CI daily.

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
> workflows on it yet.

The same key also drives AI video routes — Kling, Seedance, Hailuo, Wan, and
Vidu. Video routes require an eligible paid account group.

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

Ready-to-copy handlers for every code below live in
[`examples/error_handling.py`](examples/error_handling.py) and
[`examples/error_handling.mjs`](examples/error_handling.mjs), with the full
decision table in [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md).

- `401`: check that the key is present and the `Bearer` prefix is included.
- `402`: add balance or use an enabled account group with available quota.
- `404`: model ID not found or retired — the handler suggests the closest ID from the live catalog.
- `429`: **use the `Retry-After` header**, then bounded exponential backoff with jitter.
- `5xx`: keep the request id, retry only when the operation is safe to repeat.
- Video tasks stuck at `NOT_START 0%` for >3 min: keep the task ID and check status or usage before resubmitting — see the troubleshooting doc.

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

## 8b. Continuous verification

Every push runs [CI](.github/workflows/ci.yml): Python 3.8/3.10/3.12 and
Node 18/20 syntax checks, offline tests, and a live check that the numbers
in **every AIWaveAPI repo** still match the public pricing endpoint. CI also
runs daily, so catalog drift is caught without a commit.

Model catalogs drift. When the checker turns red it prints the exact
`file:line` and the correct value; fix all of them in one command instead of
hand-editing seven files:

```bash
python3 scripts/sync_claims.py --repo-root <path-to-all-repos>   # rewrites only the numbers
python3 scripts/verify_claims.py --repo-root <path-to-all-repos>  # must print ALL CLAIMS VERIFIED
git diff                                                        # review before committing
```

The last verified snapshot, with its UTC timestamp and pricing version, is
recorded in [`catalog-claims.json`](catalog-claims.json).

## 9. Contributing & support

Found a wrong price? That's the most useful contribution you can make — see
[CONTRIBUTING.md](CONTRIBUTING.md). For other questions, use
[Discussions](https://github.com/AIWaveAPI/aiwave-quickstart/discussions) or
open a structured [issue](https://github.com/AIWaveAPI/aiwave-quickstart/issues/new/choose).

Security issues: **do not open a public issue** — see [SECURITY.md](SECURITY.md).

## 10. Use AIWave in Claude Code

The setup script currently configures Claude Code only. It previews the field names
that will change without printing your key or existing configuration values,
retains a private backup of the original file, and refuses to overwrite edits
made after setup.

```bash
export AIWAVE_API_KEY="sk-..."                    # your own key
python3 scripts/aiwave-setup.py --dry-run        # preview, writes nothing
python3 scripts/aiwave-setup.py                  # configure Claude Code
python3 scripts/aiwave-setup.py --restore        # restore if unchanged since setup
```

The script writes the Anthropic-compatible endpoint
`https://aiwave.live/anthropic` to `~/.claude/settings.json`. Its default
model ID is `claude-sonnet-5-coding-team`; check current access and price in
the [live catalog](https://aiwave.live/api/pricing) before use. Run
`python3 scripts/test_aiwave_setup.py` and
`python3 -m unittest scripts.test_aiwave_setup_safety` for offline checks.

**Codex CLI setup is paused.** Current Codex rejects the script's former
`wire_api = "chat"` configuration. AIWave's Responses API compatibility
with Codex has not yet passed an end-to-end test, so the script refuses
`--tool codex` and `--tool both` before writing either file. Merely changing
the value to `responses` would not establish streaming, tool-call, or
continuation support. If you previously used this script for Codex,
`--restore --tool codex` can restore a verified, unchanged installation
made by the newer backup format. Older `*.aiwave.bak` files require manual
review; the script will not overwrite later edits automatically.

## Repository layout

- `examples/curl.sh` — minimal shell request
- `examples/python.py` — OpenAI Python client
- `examples/node.mjs` — OpenAI Node client
- `examples/video_curl.sh` — AI video generation + polling (curl)
- `examples/video_python.py` — video generation (submit → poll → URL)
- `examples/video_node.mjs` — same flow in Node.js
- `.env.example` — local variable names only
- `scripts/cost.py` — estimate cost from live prices
- `examples/error_handling.py` / `error_handling.mjs` — copy-paste error handlers
- `docs/TROUBLESHOOTING.md` — full error decision table

This repository contains examples, not credentials. Replace the model ID with
one that fits your workload and verify current pricing before production use.
