#!/usr/bin/env bash
# Reload SGLang policy server weights from a checkpoint on disk.
# Uses SGLang's native /update_weights_from_disk endpoint.
# No container restart, no sudo, no downtime.
#
# Usage: ./reload_sglang.sh <checkpoint_path>
# Environment:
#   POLICY_URL              - SGLang server URL (default: http://localhost:8001)
#   CHECKPOINT_MAP_FROM     - Host path prefix to replace (for containerized SGLang)
#   CHECKPOINT_MAP_TO       - Container path prefix to use instead
#
# Example: If training saves to /home/user/opensec-env/outputs/... but SGLang
# container mounts outputs at /workspace/outputs, set:
#   CHECKPOINT_MAP_FROM=/home/user/opensec-env/outputs
#   CHECKPOINT_MAP_TO=/workspace/outputs

set -euo pipefail

CHECKPOINT_PATH_ORIG="${1:?Usage: $0 <checkpoint_path>}"
POLICY_URL="${POLICY_URL:-http://localhost:8001}"

# Wait for sentinel file on the original path (training container path).
SENTINEL="${CHECKPOINT_PATH_ORIG}/READY"
for i in $(seq 1 30); do
  [ -f "$SENTINEL" ] && break
  echo "[reload] Waiting for checkpoint sentinel... (attempt $i/30)"
  sleep 2
done
[ -f "$SENTINEL" ] || { echo "[reload] ERROR: sentinel ${SENTINEL} not found after 60s"; exit 1; }

# If we saved a single model.safetensors but still have a stale index file
# pointing to shards, remove it to avoid loader confusion.
INDEX_FILE="${CHECKPOINT_PATH_ORIG}/model.safetensors.index.json"
if [ -f "${CHECKPOINT_PATH_ORIG}/model.safetensors" ] && [ -f "$INDEX_FILE" ]; then
  if ! ls "${CHECKPOINT_PATH_ORIG}"/model-*.safetensors >/dev/null 2>&1; then
    echo "[reload] Removing stale safetensors index: ${INDEX_FILE}"
    rm -f "$INDEX_FILE"
  fi
fi

# Remap to the path visible inside the SGLang container (if configured)
CHECKPOINT_PATH="${CHECKPOINT_PATH_ORIG}"
if [ -n "${CHECKPOINT_MAP_FROM:-}" ] && [ -n "${CHECKPOINT_MAP_TO:-}" ]; then
  CHECKPOINT_PATH="${CHECKPOINT_PATH_ORIG/${CHECKPOINT_MAP_FROM}/${CHECKPOINT_MAP_TO}}"
fi

echo "[reload] Updating weights from: ${CHECKPOINT_PATH}"

# SGLang native weight reload (in-place, same architecture required)
# abort_all_requests=true prevents blocking on in-flight generation requests
RESPONSE=$(curl -s -w "\n%{http_code}" -X POST \
  "${POLICY_URL}/update_weights_from_disk" \
  -H "Content-Type: application/json" \
  -d "{\"model_path\": \"${CHECKPOINT_PATH}\", \"abort_all_requests\": true}")

HTTP_CODE=$(echo "$RESPONSE" | tail -1)
BODY=$(echo "$RESPONSE" | head -n -1)

if [ "$HTTP_CODE" -ne 200 ]; then
  echo "[reload] ERROR: /update_weights_from_disk returned HTTP ${HTTP_CODE}"
  echo "[reload] Response: ${BODY}"
  exit 1
fi

echo "[reload] Weights updated successfully."
echo "[reload] Response: ${BODY}"

# Verify server is healthy after reload
curl -sf "${POLICY_URL}/health" > /dev/null || {
  echo "[reload] WARNING: health check failed after reload"
  exit 1
}

# Clean up sentinel so stale markers don't confuse future reloads
rm -f "$SENTINEL"

echo "[reload] Server healthy with new weights."
