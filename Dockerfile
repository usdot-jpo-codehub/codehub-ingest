# FROM java:8
#FROM alpine:3.8
FROM python:3.7-alpine

ARG SONAR_MYSQL_ENDPOINT

ENV SONAR_VERSION=6.1 \
    SONARQUBE_HOME=/opt/sonarqube \
    SONAR_RUNNER_VERSION=2.4 \
    SONAR_RUNNER_HOME=/opt/sonar-runner \
    # Database configuration
    # Defaults to using H2
    SONARQUBE_JDBC_USERNAME=sonar \
    SONARQUBE_JDBC_PASSWORD=sonar \
    SONARQUBE_JDBC_URL=$SONAR_MYSQL_ENDPOINT

ENV JAVA_HOME="/usr/lib/jvm/java-1.8-openjdk"

# Http port (for local testing)
# EXPOSE 9000

RUN apk update \
    && apk upgrade \
    && apk add --no-cache bash \
    && apk add --no-cache --virtual=build-dependencies unzip \
    && apk add --no-cache curl \
    && apk add --no-cache openjdk8-jre \
    && apk add --no-cache git \
    && apk add --no-cache clamav

RUN apk add --no-cache python3 \
    && python3 -m ensurepip \
    && pip3 install --upgrade pip setuptools \
    && rm -r /usr/lib/python*/ensurepip && \
    if [ ! -e /usr/bin/pip ]; then ln -s pip3 /usr/bin/pip ; fi && \
    if [[ ! -e /usr/bin/python ]]; then ln -sf /usr/bin/python3 /usr/bin/python; fi && \
    rm -r /root/.cache

RUN set -x \
    # && mkdir /opt \
    && cd /opt \
    && curl -o sonarqube.zip -fSL https://binaries.sonarsource.com/Distribution/sonarqube/sonarqube-$SONAR_VERSION.zip \
    && unzip sonarqube.zip \
    && mv sonarqube-$SONAR_VERSION sonarqube \
    && rm sonarqube.zip* \
    && rm -rf $SONARQUBE_HOME/bin/*

RUN cd /opt \
    && curl -o sonar_runner.zip -fSL http://repo1.maven.org/maven2/org/codehaus/sonar/runner/sonar-runner-dist/$SONAR_RUNNER_VERSION/sonar-runner-dist-$SONAR_RUNNER_VERSION.zip \
    && unzip sonar_runner.zip \
    && mv sonar-runner-$SONAR_RUNNER_VERSION sonar-runner \
    && rm sonar_runner.zip

RUN cd $SONARQUBE_HOME/extensions/plugins \
    && curl -o sonar-java-plugin-4.2.jar -fSL http://binaries.sonarsource.com/Distribution/sonar-java-plugin/sonar-java-plugin-4.2.jar \
    && curl -o sonar-javascript-plugin-2.15.jar -fSL http://binaries.sonarsource.com/Distribution/sonar-javascript-plugin/sonar-javascript-plugin-2.15.jar \
    && curl -o sonar-csharp-plugin-5.3.2.jar -fSL http://binaries.sonarsource.com/Distribution/sonar-csharp-plugin/sonar-csharp-plugin-5.3.2.jar \
    && curl -o sonar-python-plugin-1.6.jar -fSL http://binaries.sonarsource.com/Distribution/sonar-python-plugin/sonar-python-plugin-1.6.jar \
    && curl -o sonar-groovy-plugin-1.3.1.jar -fSL http://binaries.sonarsource.com/Distribution/sonar-groovy-plugin/sonar-groovy-plugin-1.3.1.jar \
    && curl -o sonar-ldap-plugin-1.5.1.jar -fSL http://binaries.sonarsource.com/Distribution/sonar-ldap-plugin/sonar-ldap-plugin-1.5.1.jar \
    && curl -o sonar-php-plugin-2.7.jar -fSL http://binaries.sonarsource.com/Distribution/sonar-php-plugin/sonar-php-plugin-2.7.jar \
    && curl -o sonar-xml-plugin-1.3.jar -fSL http://binaries.sonarsource.com/Distribution/sonar-xml-plugin/sonar-xml-plugin-1.3.jar \
    && curl -o sonar-web-plugin-2.4.jar -fSL http://binaries.sonarsource.com/Distribution/sonar-web-plugin/sonar-web-plugin-2.4.jar \
    && curl -o sonar-scm-git-plugin-1.2.jar -fSL http://binaries.sonarsource.com/Distribution/sonar-scm-git-plugin/sonar-scm-git-plugin-1.2.jar \
    && curl -o sonar-scm-svn-plugin-1.3.jar -fSL http://binaries.sonarsource.com/Distribution/sonar-scm-svn-plugin/sonar-scm-svn-plugin-1.3.jar

RUN freshclam


VOLUME ["$SONARQUBE_HOME/data", "$SONARQUBE_HOME/extensions"]

WORKDIR $SONARQUBE_HOME
COPY docker-entrypoint.sh $SONARQUBE_HOME/bin/
COPY ingest /opt/ingest
RUN cd /opt/ingest \
    && pip install -r ./requirements.txt

RUN chmod +x $SONARQUBE_HOME/bin/docker-entrypoint.sh
ENTRYPOINT ["./bin/docker-entrypoint.sh"]
