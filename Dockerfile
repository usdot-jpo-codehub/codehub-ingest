FROM python:3.7-alpine

# ARG SONAR_API_BASE_URL

ENV JAVA_HOME="/usr/lib/jvm/java-1.8-openjdk"

ENV SONAR_RUNNER_VERSION=2.4 \
    SONAR_RUNNER_HOME=/opt/sonar-runner 

# Http port (for local testing)
# EXPOSE 9000

RUN apk update \
    && apk upgrade \
    && apk add --no-cache bash \
    && apk add --no-cache --virtual=build-dependencies unzip \
    && apk add --no-cache curl \
    && apk add --no-cache openjdk8-jre \
    && apk add --no-cache git \
    && apk add --no-cache clamav \
    && apk add gettext libintl \
    && mv /usr/bin/envsubst /usr/local/sbin/envsubst 

RUN apk add --no-cache python3 \
    && python3 -m ensurepip \
    && pip3 install --upgrade pip setuptools \
    && rm -r /usr/lib/python*/ensurepip && \
    if [ ! -e /usr/bin/pip ]; then ln -s pip3 /usr/bin/pip ; fi && \
    if [[ ! -e /usr/bin/python ]]; then ln -sf /usr/bin/python3 /usr/bin/python; fi && \
    rm -r /root/.cache


RUN cd /opt \
    && curl -o sonar_runner.zip -fSL http://repo1.maven.org/maven2/org/codehaus/sonar/runner/sonar-runner-dist/$SONAR_RUNNER_VERSION/sonar-runner-dist-$SONAR_RUNNER_VERSION.zip \
    && unzip sonar_runner.zip \
    && mv sonar-runner-$SONAR_RUNNER_VERSION sonar-runner \
    && rm sonar_runner.zip \
    && rm sonar-runner/conf/sonar-runner.properties \
    && echo "sonar.host.url='${SONAR_API_BASE_URL}'" >> sonar-runner/conf/sonar-runner.properties


RUN freshclam


COPY docker-entrypoint.sh /opt/
COPY ingest /opt/ingest
RUN cd /opt/ingest \
    && pip install -r ./requirements.txt

RUN chmod +x opt/docker-entrypoint.sh
ENTRYPOINT ["opt/docker-entrypoint.sh"]
