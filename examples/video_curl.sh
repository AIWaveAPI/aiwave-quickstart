#!/usr/bin/env bash
# AIWave video generation quickstart. Requires curl and Python 3.
# Video routes are experimental and may require a paid account group.
# Keep task IDs: an uncertain POST outcome must not be blindly resubmitted.
set -Eeuo pipefail
: "${AIWAVE_API_KEY:?Set AIWAVE_API_KEY first}"
BASE_URL="${AIWAVE_BASE_URL:-https://aiwave.live/v1}"
MODEL="${AIWAVE_VIDEO_MODEL:-kling-v2-6}"
PROMPT="${1:-A red sports car drifting through a neon-lit city at night, cinematic tracking shot, rain reflections}"

# Let a JSON encoder handle quotes, backslashes, Unicode and newlines.
PAYLOAD=$(python3 -c 'import json,sys; print(json.dumps({"model":sys.argv[1],"prompt":sys.argv[2]}))' "$MODEL" "$PROMPT")

echo "==> Submitting video job ($MODEL)..."
if ! RESP=$(curl --silent --show-error --fail-with-body --max-time 120 \
  "$BASE_URL/video/generations" \
  -H "Authorization: Bearer $AIWAVE_API_KEY" \
  -H "Content-Type: application/json" \
  --data-binary "$PAYLOAD"); then
  echo "!! Submission outcome unknown. Check usage or task history before another billable POST." >&2
  exit 1
fi

if ! TASK_ID=$(printf '%s' "$RESP" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d.get("task_id") or d.get("id") or "")'); then
  echo "!! Invalid submission response. Check usage or task history before resubmitting." >&2
  exit 1
fi
if [ -z "$TASK_ID" ]; then
  echo "!! No task ID in submission response. Check usage or task history before resubmitting." >&2
  exit 1
fi

echo "==> Task ID: $TASK_ID"
echo "==> Polling every 15s, up to 15 min..."
for i in $(seq 1 60); do
  sleep 15
  if ! STATUS=$(curl --silent --show-error --fail-with-body --max-time 30 \
    "$BASE_URL/video/generations/$TASK_ID" \
    -H "Authorization: Bearer $AIWAVE_API_KEY"); then
    echo "!! Status lookup failed. Keep task ID $TASK_ID and retry the GET later." >&2
    exit 1
  fi
  if ! ST=$(printf '%s' "$STATUS" | python3 -c 'import json,sys; d=json.load(sys.stdin); d=d.get("data") or d; print(d.get("status") or "")'); then
    echo "!! Invalid status response. Keep task ID $TASK_ID." >&2
    exit 1
  fi
  PROG=$(printf '%s' "$STATUS" | python3 -c 'import json,sys; d=json.load(sys.stdin); d=d.get("data") or d; print(d.get("progress") or "")')
  echo "  [$((i*15))s] $ST $PROG"
  case "$ST" in
    SUCCESS) printf '%s\n' "$STATUS"; exit 0;;
    FAILURE) echo "!! Failed: $STATUS" >&2; exit 1;;
  esac
done
echo "!! Timed out after 15 min. Keep task ID $TASK_ID and check status later." >&2
exit 1
