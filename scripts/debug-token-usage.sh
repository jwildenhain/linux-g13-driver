#!/usr/bin/env bash
set -euo pipefail

echo "=== Token Usage Debug ==="

echo
if ! command -v curl >/dev/null 2>&1; then
  echo "curl is required"
  exit 1
fi
if ! command -v jq >/dev/null 2>&1; then
  echo "jq is required"
  exit 1
fi

echo "Environment:"
echo "  OPENAI_API_KEY: ${OPENAI_API_KEY:+SET}"
echo "  ANTIGRAVITY_API_KEY: ${ANTIGRAVITY_API_KEY:+SET}"
echo "  ANTIGRAVITY_USAGE_URL: ${ANTIGRAVITY_USAGE_URL:-not set}"
echo "  GEMINI_API_KEY: ${GEMINI_API_KEY:+SET}"
echo "  GEMINI_USAGE_URL: ${GEMINI_USAGE_URL:-not set}"

echo

today=$(date +%F)

fetch_json() {
  local label="$1"
  local url="$2"
  shift 2

  echo "[$label]"
  echo "URL: $url"

  if [[ -z "$url" ]]; then
    echo "  URL not set"
    echo
    return
  fi

  local curl_args=("-L" "--compressed" "--max-time" "8" "-w" "\nHTTP_STATUS=%{http_code}\\n")
  local output
  local status

  if ! output=$(curl "${curl_args[@]}" "$@" "$url" 2>/tmp/token_debug_curl.err); then
    echo "  curl command failed"
    if [[ -s /tmp/token_debug_curl.err ]]; then
      echo "  error: $(cat /tmp/token_debug_curl.err)"
    fi
    echo
    return
  fi

  rm -f /tmp/token_debug_curl.err

  status=$(printf '%s' "$output" | awk -F= '/^HTTP_STATUS=/{print $2}' | tail -n1)
  local json
  json=$(printf '%s' "$output" | sed -n '1,/^HTTP_STATUS=/{/HTTP_STATUS=/{q;p}}')

  echo "  HTTP status: ${status:-unknown}"
  if [[ -z "$json" ]]; then
    echo "  empty response"
    echo
    return
  fi

  echo "  raw length: ${#json}"
  echo "  raw sample: $(printf '%s' "$json" | cut -c1-260)"
  echo "  parsed keys:"
  if printf '%s' "$json" | jq 'keys' >/tmp/token_debug_jq.out 2>/tmp/token_debug_jq.err; then
    sed 's/^/    /' /tmp/token_debug_jq.out
  else
    echo '    <not an object>'
  fi
  echo
}

if [[ -n "${OPENAI_API_KEY:-}" ]]; then
  fetch_json "OpenAI Usage" "https://api.openai.com/v1/dashboard/billing/usage?start_date=$today&end_date=$today" \
    -H "Authorization: Bearer ${OPENAI_API_KEY}"
  fetch_json "OpenAI Subscription" "https://api.openai.com/v1/dashboard/billing/subscription" \
    -H "Authorization: Bearer ${OPENAI_API_KEY}"
else
  echo "[OpenAI Usage] OPENAI_API_KEY not set"
  echo
  echo "[OpenAI Subscription] OPENAI_API_KEY not set"
  echo
fi

if [[ -n "${ANTIGRAVITY_API_KEY:-}" && -n "${ANTIGRAVITY_USAGE_URL:-}" ]]; then
  fetch_json "Antigravity" "$ANTIGRAVITY_USAGE_URL" \
    -H "Authorization: Bearer ${ANTIGRAVITY_API_KEY}"
elif [[ -n "${ANTIGRAVITY_USAGE_URL:-}" || -n "${ANTIGRAVITY_API_KEY:-}" ]]; then
  echo "[Antigravity] usage URL or API key missing"
  echo "  ANTIGRAVITY_USAGE_URL=${ANTIGRAVITY_USAGE_URL:-not set}"
  echo "  ANTIGRAVITY_API_KEY=${ANTIGRAVITY_API_KEY:+SET}"
  echo
fi

if [[ -n "${GEMINI_API_KEY:-}" && -n "${GEMINI_USAGE_URL:-}" ]]; then
  fetch_json "Gemini" "$GEMINI_USAGE_URL" \
    -H "x-goog-api-key: ${GEMINI_API_KEY}"
elif [[ -n "${GEMINI_USAGE_URL:-}" || -n "${GEMINI_API_KEY:-}" ]]; then
  echo "[Gemini] usage URL or API key missing"
  echo "  GEMINI_USAGE_URL=${GEMINI_USAGE_URL:-not set}"
  echo "  GEMINI_API_KEY=${GEMINI_API_KEY:+SET}"
  echo
fi

