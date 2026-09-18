#!/usr/bin/env bash
set -Eeuo pipefail
: "${AIWAVE_API_KEY:?Set AIWAVE_API_KEY first}"
BASE_URL="${AIWAVE_BASE_URL:-https://aiwave.live/v1}"
MODEL="${AIWAVE_MODEL:-deepseek-v4-flash}"

curl "$BASE_URL/chat/completions" \
  -H "Authorization: Bearer $AIWAVE_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{\"model\":\"$MODEL\",\"messages\":[{\"role\":\"user\",\"content\":\"Say hello in one sentence.\"}],\"max_tokens\":32}"
