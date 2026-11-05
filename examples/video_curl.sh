#!/usr/bin/env bash
# AIWave video generation quickstart: submit a Kling job, poll until done.
# EXPERIMENTAL: the video endpoint occasionally surfaces upstream channel
# errors. Video routes require a paid account group (from $5).
#
# Battle-tested notes (from real productions, 2026-10):
#   - Generation takes 5-11 minutes for a single shot. Poll every 15s,
#     give up after 15 minutes.
#   - Some upstream channels stall without a reference image. If a task
#     stays NOT_START for >3 minutes with 0% progress, keep its task ID and
#     check status or usage before submitting another billable job.
set -Eeuo pipefail
: "${AIWAVE_API_KEY:?Set AIWAVE_API_KEY first}"
BASE_URL="${AIWAVE_BASE_URL:-https://aiwave.live/v1}"
MODEL="${AIWAVE_VIDEO_MODEL:-kling-v2-6}"
PROMPT="${1:-A red sports car drifting through a neon-lit city at night, cinematic tracking shot, rain reflections}"

echo "==> Submitting video job ($MODEL)..."
RESP=$(curl -s "$BASE_URL/video/generations" \
  -H "Authorization: Bearer $AIWAVE_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{\"model\":\"$MODEL\",\"prompt\":\"$PROMPT\"}")

echo "$RESP"

TASK_ID=$(echo "$RESP" | grep -oE '"task_id":"[^"]+"' | head -1 | cut -d'"' -f4)
if [ -z "$TASK_ID" ]; then
  echo "!! No task_id in response �� see above. Video routes may need a paid group."
  exit 1
fi

echo "==> Polling $TASK_ID (every 15s, up to 15 min)..."
for i in $(seq 1 60); do
  sleep 15
  STATUS=$(curl -s "$BASE_URL/video/generations/$TASK_ID" \
    -H "Authorization: Bearer $AIWAVE_API_KEY")
  ST=$(echo "$STATUS" | grep -oE '"status":"[^"]+"' | head -1 | cut -d'"' -f4)
  PROG=$(echo "$STATUS" | grep -oE '"progress":"[^"]*"' | head -1 | cut -d'"' -f4)
  echo "  [$((i*15))s] $ST $PROG"
  case "$ST" in
    SUCCESS) echo "$STATUS" | grep -oE '"https?://[^"]+\.(mp4|mov)[^"]*"' | head -1; exit 0;;
    FAILURE) echo "!! Failed:"; echo "$STATUS"; exit 1;;
  esac
done
echo "!! Timed out after 15 min �� last status:"
echo "$STATUS"
