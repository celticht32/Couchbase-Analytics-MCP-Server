#!/usr/bin/env bash
# Initialize a fresh Couchbase Enterprise node with Analytics service for CI.
set -euo pipefail

HOST=${CB_HOST:-localhost}
PORT=${CB_PORT:-8091}
USERNAME=${CB_REST_USERNAME:-Administrator}
PASSWORD=${CB_REST_PASSWORD:-password}
ANALYTICS_PORT=${CB_ANALYTICS_PORT:-8095}

BASE="http://${HOST}:${PORT}"

echo "Waiting for Couchbase REST API..."
until curl -sf "${BASE}/pools" >/dev/null 2>&1; do sleep 2; done

STATUS=$(curl -s -o /dev/null -w "%{http_code}" "${BASE}/pools/default")
if [ "$STATUS" = "200" ]; then
  echo "Already initialized."
  exit 0
fi

echo "Initializing node..."
curl -sf -X POST "${BASE}/nodes/self/controller/settings" \
  -d "path=%2Fopt%2Fcouchbase%2Fvar%2Flib%2Fcouchbase%2Fdata" \
  -d "analyticsPath=%2Fopt%2Fcouchbase%2Fvar%2Flib%2Fcouchbase%2Fdata"

echo "Setting services (kv + cbas)..."
curl -sf -X POST "${BASE}/node/controller/setupServices" \
  -d "services=kv%2Ccbas"

echo "Setting credentials..."
curl -sf -X POST "${BASE}/settings/web" \
  -d "username=${USERNAME}" -d "password=${PASSWORD}" -d "port=${PORT}"

echo "Setting memory quotas..."
curl -sf -X POST "${BASE}/pools/default" \
  -u "${USERNAME}:${PASSWORD}" \
  -d "clusterName=cb-analytics-test" \
  -d "memoryQuota=512" \
  -d "cbasMemoryQuota=1024"

echo "Waiting for Analytics service..."
until curl -sf -u "${USERNAME}:${PASSWORD}" \
    "http://${HOST}:${ANALYTICS_PORT}/api/v1/status/service" >/dev/null 2>&1; do
  sleep 3
done

echo "Initialization complete."
