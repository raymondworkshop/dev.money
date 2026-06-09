#!/bin/zsh
# Sync wiki with local MLX, then build and deploy the Quartz site.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ -f "${ROOT}/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "${ROOT}/.env"
  set +a
fi

LOG_DIR="${ROOT}/logs"
mkdir -p "$LOG_DIR"
PUBLISH_LOG="${LOG_DIR}/publish.log"
exec > >(tee -a "$PUBLISH_LOG") 2>&1
echo "=== publish $(date -Iseconds) ==="

LLM_PROVIDER="${LLM_PROVIDER:-mlx}"
LLM_URL="${LLM_URL:-http://127.0.0.1:8080/v1/chat/completions}"
LLM_WAIT_SECONDS="${LLM_WAIT_SECONDS:-180}"
DEPLOY="${DEPLOY:-1}"
DRY_RUN="${DRY_RUN:-}"

wait_for_mlx() {
  if [[ "$LLM_PROVIDER" != "mlx" ]]; then
    return 0
  fi

  local base="${LLM_URL%/chat/completions}"
  local deadline=$((SECONDS + LLM_WAIT_SECONDS))
  while (( SECONDS < deadline )); do
    if curl -fsS --max-time 5 "${base}/models" >/dev/null 2>&1; then
      echo "[publish] MLX ready at ${base}"
      return 0
    fi
    echo "[publish] waiting for MLX at ${base}..."
    sleep 5
  done

  echo "[publish] MLX not reachable after ${LLM_WAIT_SECONDS}s" >&2
  return 1
}

echo "[publish] sync wiki (LLM_PROVIDER=${LLM_PROVIDER})"
wait_for_mlx
SYNC_EXIT=0
if [[ -n "$DRY_RUN" ]]; then
  make sync LLM_PROVIDER="$LLM_PROVIDER" DRY_RUN=1 || SYNC_EXIT=$?
else
  make sync LLM_PROVIDER="$LLM_PROVIDER" || SYNC_EXIT=$?
fi
if (( SYNC_EXIT != 0 )); then
  echo "[publish] sync finished with failures (exit=${SYNC_EXIT}); continuing with deploy=${DEPLOY}"
fi

if [[ "$DEPLOY" == "1" ]]; then
  if [[ ! -d site/node_modules ]]; then
    echo "[publish] installing site dependencies"
    make site-install
  fi
  echo "[publish] build and deploy site"
  make site-deploy
else
  echo "[publish] DEPLOY=0, skipping site deploy"
fi

echo "[publish] done"
echo "[publish] production: https://news-wiki.pages.dev/"
