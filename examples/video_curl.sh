#!/usr/bin/env bash
# AIWave video generation quickstart: submit a Kling job, poll until done.
# Video routes require a paid account group (from $5). See aiwave.live/models
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

# Task id extraction is response-shape dependent; print the response above
# and take the task id from it, then poll:
#   curl "https://aiwave.live/v1/query/video_generation?task_id=TASK_ID" \
#     -H "Authorization: Bearer $AIWAVE_API_KEY"
# Poll every 10-15s until the response contains a video URL.
