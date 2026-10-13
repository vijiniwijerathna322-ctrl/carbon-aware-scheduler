#!/usr/bin/env bash
set -euo pipefail

# Override PORT for an already occupied host port; avoid deleting named containers.
image="${IMAGE:-carbon-scheduler:smoke}"
port="${PORT:-8000}"
container=""
work="$(mktemp -d)"
if command -v python3 >/dev/null; then
  python_command=python3
elif command -v python >/dev/null; then
  python_command=python
elif [[ -x .venv/Scripts/python.exe ]]; then
  python_command=.venv/Scripts/python.exe
else
  echo 'Python 3 is required for response assertions.' >&2
  rmdir "$work"
  exit 1
fi
cleanup() {
  if [[ -n "$container" ]]; then
    docker rm -f "$container" >/dev/null
  fi
  rm -f "$work/forecast.json" "$work/schedule.json" "$work/monitor.json"
  rmdir "$work"
}
trap cleanup EXIT

case "${SMOKE_MODE:-build}" in
  build) docker build -t "$image" . ;;
  local) docker image inspect "$image" >/dev/null ;;
  pull) docker pull "$image" ;;
  *) echo 'SMOKE_MODE must be build, local or pull.' >&2; exit 1 ;;
esac
container="$(docker run -d --read-only --tmpfs /tmp:rw,noexec,nosuid,size=64m \
  --cap-drop ALL --security-opt no-new-privileges -p "127.0.0.1:$port:8000" "$image")"
for _ in $(seq 1 30); do
  if curl --fail --silent "http://127.0.0.1:$port/healthz" >/dev/null; then
    break
  fi
  sleep 1
done
curl --fail --silent "http://127.0.0.1:$port/healthz" >/dev/null || {
  docker logs "$container"
  exit 1
}
curl --fail --silent "http://127.0.0.1:$port/v1/forecast?horizon=6" > "$work/forecast.json"
monitor_status="$(curl --silent --output "$work/monitor.json" --write-out '%{http_code}' \
  "http://127.0.0.1:$port/v1/monitoring/status")"
test "$monitor_status" = "404"
"$python_command" - "$work/monitor.json" <<'PY'
import json
import sys
assert json.load(open(sys.argv[1])) == {'error': 'no_report'}
PY
payload="$("$python_command" - "$work/forecast.json" <<'PY'
import json
import sys
from datetime import datetime, timedelta

forecast = json.load(open(sys.argv[1]))
assert len(forecast['points']) == 6
assert {'issue_time', 'data_as_of', 'model_version', 'alpha'} <= forecast.keys()
issue = datetime.fromisoformat(forecast['issue_time'].replace('Z', '+00:00'))
print(json.dumps({'duration_hours': 2, 'power_kw': 7,
                  'deadline': (issue + timedelta(hours=24)).isoformat()}))
PY
)"
curl --fail --silent -H 'Content-Type: application/json' -d "$payload" \
  "http://127.0.0.1:$port/v1/schedule" > "$work/schedule.json"
"$python_command" - "$work/schedule.json" <<'PY'
import json
import sys
result = json.load(open(sys.argv[1]))
assert {'recommendation', 'forecast_issue_time', 'data_as_of', 'model_version', 'notes'} <= result.keys()
assert result['recommendation']['end'] > result['recommendation']['start']
PY
test "$(docker exec "$container" id -u)" != "0"
docker image inspect "$image" --format 'Image size: {{.Size}} bytes'
echo 'Docker offline, non-root, read-only smoke test passed.'
