#!/usr/bin/env bash
set -euo pipefail

BASE_MANIFEST="https://registry.enrg.local"
BASE_PROVISIONING="https://provisioning.enrg.local"
API_KEY="${API_KEY:-dev-token}"

echo "== POST /manifests =="
curl -sS -X POST "$BASE_MANIFEST/manifests" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  --data-binary @examples/device-manifest.sample.json | jq .

echo
echo "== POST /devices (provisioning) =="
curl -sS -X POST "$BASE_PROVISIONING/devices" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  --data-binary @examples/device-proof.provisioning.sample.json | jq .
