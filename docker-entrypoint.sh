#!/usr/bin/env bash
# Entry points for the image (task T8):
#   serve          start the API on $PORT (default 8080)
#   train [args]   run the training pipeline (src/train.py, from T11)
#   anything else  run it as a command, e.g. `bash` or `pytest`
set -euo pipefail

case "${1:-serve}" in
  serve)
    exec uvicorn src.api.main:app --host 0.0.0.0 --port "${PORT:-8080}"
    ;;
  train)
    shift
    exec python -m src.train "$@"
    ;;
  *)
    exec "$@"
    ;;
esac
