#!/usr/bin/env bash
# Deploy the dashboard on the Pi: update the checkout, rebuild the web app,
# restart the web service, and check it answers. The API service needs root,
# so this script prints the command instead of running it.
#
# Usage: scripts/deploy_pi.sh <branch>
set -euo pipefail

BRANCH="${1:?usage: scripts/deploy_pi.sh <branch>}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "== update checkout to ${BRANCH}"
git fetch origin
git checkout "$BRANCH"
git pull --ff-only origin "$BRANCH"

echo "== build web app"
(cd web && npm run build)

echo "== restart web service"
systemctl --user restart sector-next
sleep 6
if curl -fsS -o /dev/null http://127.0.0.1:3100/; then
  echo "web: up"
else
  echo "web: NOT answering on 127.0.0.1:3100 (check: systemctl --user status sector-next)" >&2
  exit 1
fi

echo "== API service (needs your sudo password, run it yourself):"
echo "   sudo systemctl restart sector-api"
echo "   then: curl -s http://127.0.0.1:8001/api/v1/health"
