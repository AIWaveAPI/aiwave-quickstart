# AIWave Quickstart

Call Chinese AI models through one OpenAI-compatible endpoint. Keep your
client code stable while you choose a model for the job.

## 1. Set your environment

Create a key in the [AIWave console](https://aiwave.live/register?aff=CcyF), then export it locally:

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
  -d "{\"model\":\"$AIWAVE_MODEL\",\"messages\":[{\"role\":\"user\",\"content\":\"Say hello in one sentence.\"}],\"max_tokens\":32}"
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

## 4. Handle the common responses

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
- `.env.example` — local variable names only

This repository contains examples, not credentials. Replace the model ID with
one that fits your workload and verify current pricing before production use.
