# Troubleshooting

Every code below has a runnable counterpart in
[`examples/error_handling.py`](../examples/error_handling.py) and
[`examples/error_handling.mjs`](../examples/error_handling.mjs).
Copy the handler instead of writing your own.

## 401 — authentication failed

| | |
|---|---|
| **Means** | The key is missing, malformed, or not accepted. |
| **First check** | Use `if [ -n "${AIWAVE_API_KEY:-}" ]; then printf 'AIWAVE_API_KEY is set\n'; else printf 'AIWAVE_API_KEY is missing\n'; fi` to confirm the variable is present without printing its value. Check that your request uses `Authorization: Bearer <key>`; the word `Bearer` and the space are required. Never paste the key or an unredacted request into an issue. |
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
| **Fix** | Honor the server's `Retry-After`. If it exceeds 60 seconds, the example stops automatic retries and reports the delay. Without the header, it uses bounded exponential backoff with jitter (up to 30 seconds). Avoid stacking retries on top of an SDK's own retry policy. |
| **Retry?** | Yes, with backoff. |

## 5xx — server or upstream error

| | |
|---|---|
| **Means** | Our gateway or an upstream vendor failed. |
| **First check** | Save the `x-request-id` response header — support can find the exact log line. |
| **Common causes** | Upstream vendor incident; timeout on a very long generation; transient network. |
| **Fix** | Do not retry automatically. The upstream may have completed the request even if this response failed. Keep the request ID, inspect usage or task status, then decide whether a new request is acceptable. |
| **Retry?** | No automatic retry; decide manually after checking the first request. |

## Video tasks stuck at NOT_START / 0%

This is not an HTTP error code. An accepted video task can remain at
`NOT_START` with 0% progress without a terminal provider result. The display
alone does not establish whether the task failed, is queued, or incurred cost.

**Heuristic:** if a task stays at `NOT_START` with 0% progress for more than
3 minutes, keep the task ID and check its status or usage before submitting another task. See
[`examples/video_python.py`](../examples/video_python.py), which implements
this check. The 3-minute threshold is an example review prompt, not a provider timeout or a reason to resubmit automatically.

## Still stuck?

Open a [structured issue](https://github.com/AIWaveAPI/aiwave-quickstart/issues/new/choose)
with the model ID, client version, a redacted curl reproduction, and (for 5xx)
the request id. Never paste real keys — use `sk-REDACTED`.
