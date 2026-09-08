#!/usr/bin/env sh
# Worker entrypoint — runs the background loop process.
set -e
cd /srv/services/worker
export PYTHONPATH="/srv/services/api:/srv/services/worker"
exec python -m main