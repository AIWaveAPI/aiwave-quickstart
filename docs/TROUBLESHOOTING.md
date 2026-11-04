# Troubleshooting

Every code below has a runnable counterpart in
[`examples/error_handling.py`](../examples/error_handling.py) and
[`examples/error_handling.mjs`](../examples/error_handling.mjs).
Copy the handler instead of writing your own.

## 401 — authentication failed

| | |
|---|---|
| **Means** | The key is missing, malformed, or not accepted. |
| **First check** | `echo $AIWAVE_API_KEY` — is it set? Does the header say `Authorization: Bearer <key>`? The word `Bearer` and the space are required. |
| **Common causes** | Key rotated in the console; key copied with a trailing newline; key from another provider; using `api-key:` instead of `Authorization`. |
| **Fix** | Create a key at https://aiwave.live/register, store it in a secret manager, never in source. |
| **Retry?** | No. |

## 402 — insufficient balance

| | |
|---|---|
| **Means** | The account has no balance, or the enabled group has no available quota. |
| **First check** | Balance in the console; confirm which group your token is using. |
| **Common causes** | New account with only the starting credit; group switched; quota exhausted mid-run. |
| **Fix** | Add balance at https://aiwave.live/pricing, or use a group with quota. |
| **Retry?** | No — retrying only burns time. |

## 404 — model not found

| | |
|---|---|
| **Means** | The model ID does not exist, is retired, or is not enabled for your group. |
| **First check** | Copy the exact ID from https://aiwave.live/models. Model IDs are case-sensitive and change as vendors retire versions. |
| **Common causes** | Typo (`deepsek-…`); using an old ID from a stale blog post; requesting a paid-tier-only route from a free-tier token. |
| **Fix** | Our handler queries the live catalog and suggests the closest current IDs. |
| **Retry?** | No. |

## 429 — rate limited

| | |
|---|---|
| **Means** | You exceeded a per-minute or per-group request limit. |
| **First check** | The `Retry-After` response header — **it wins over any local backoff**. |
| **Common causes** | Parallel scripts; frontend auto-refresh; no jitter (all clients retry at the same instant). |
| **Fix** | Bounded exponential backoff with jitter. Our handler caps waits at 30s and stops after a bounded number of attempts. Note that OpenAI's official Python/Node SDKs retry 429 twice by default — don't stack another retry loop on top of that. |
| **Retry?** | Yes, with backoff. |

## 5xx — server or upstream error

| | |
|---|---|
| **Means** | Our gateway or an upstream vendor failed. |
| **First check** | Save the `x-request-id` response header — support can find the exact log line. |
| **Common causes** | Upstream vendor incident; timeout on a very long generation; transient network. |
| **Fix** | Retry **only when the operation is safe to repeat**. Chat completions are; a paid video/ generation job may submit twice. Check the service status page before mass retries. |
| **Retry?** | Yes, cautiously. |

## Video tasks stuck at NOT_START / 0%

Not an HTTP error code, but the most common support question. Some upstream
video channels silently fail when no reference image is supplied: the task is
accepted (HTTP 200) but never starts, and no error is returned.

**Heuristic:** if a task stays at `NOT_START` with 0% progress for more than
3 minutes, treat it as an upstream failure and submit a new task. Don't wait
15 minutes. See
[`examples/video_python.py`](../examples/video_python.py), which implements
this check. A single shot normally takes 5-11 minutes.

## Still stuck?

Open a [structured issue](https://github.com/AIWaveAPI/aiwave-quickstart/issues/new/choose)
with the model ID, client version, a redacted curl reproduction, and (for 5xx)
the request id. Never paste real keys — use `sk-REDACTED`.
