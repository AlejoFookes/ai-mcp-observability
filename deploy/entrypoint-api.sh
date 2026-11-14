#!/bin/sh
set -eu

if [ "${RUN_MIGRATIONS:-1}" = "1" ]; then
  echo "multimcp-api: running alembic upgrade head"
  alembic upgrade head
fi

exec "$@"
