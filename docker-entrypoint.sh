#!/bin/bash

set -e

if [ "${1:0:1}" != '-' ]; then
  exec "$@"
fi

echo 'Sonar URL: '
echo $SONARQUBE_JDBC_URL

exec java -jar lib/sonar-application-$SONAR_VERSION.jar \
  -Dsonar.log.console=true \
  -Dsonar.jdbc.username="$SONARQUBE_JDBC_USERNAME" \
  -Dsonar.jdbc.password="$SONARQUBE_JDBC_PASSWORD" \
  -Dsonar.jdbc.url="$SONARQUBE_JDBC_URL" \
  -Dsonar.web.javaAdditionalOpts="$SONARQUBE_WEB_JVM_OPTS -Djava.security.egd=file:/dev/./urandom" \
  "$@" &

echo 'Waiting 90 seconds, then running ingest'
sleep 90
cd /opt/ingest
echo 'Running ingest'

exec python ./ingest.py