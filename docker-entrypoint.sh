#!/bin/bash

set -e

if [ "${1:0:1}" != '-' ]; then
  exec "$@"
fi

envsubst '${SONAR_API_BASE_URL}' < /opt/sonar-runner/conf/sonar-runner.properties.template > /opt/sonar-runner/conf/sonar-runner.properties

cd /opt/ingest
echo 'Running ingest'

exec python ./ingest.py