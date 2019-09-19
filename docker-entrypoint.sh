#!/bin/bash

set -e

if [ "${1:0:1}" != '-' ]; then
  exec "$@"
fi

cd /opt/ingest
echo 'Running ingest'

exec python ./ingest.py