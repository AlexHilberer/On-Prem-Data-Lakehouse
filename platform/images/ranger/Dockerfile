FROM maven:3.9.11-eclipse-temurin-8 AS builder

ARG RANGER_VERSION=2.8.0
ARG RANGER_URL=https://downloads.apache.org/ranger/${RANGER_VERSION}/apache-ranger-${RANGER_VERSION}.tar.gz

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl python3 \
    && rm -rf /var/lib/apt/lists/*
RUN groupadd --system ranger && useradd --system --gid ranger --home /var/lib/ranger ranger
WORKDIR /src
RUN curl --fail --location --retry 5 "${RANGER_URL}" -o "apache-ranger-${RANGER_VERSION}.tar.gz" \
    && curl --fail --location --retry 5 "${RANGER_URL}.sha512" -o ranger.sha512 \
    && sha512sum --check ranger.sha512 \
    && tar -xzf "apache-ranger-${RANGER_VERSION}.tar.gz" --strip-components=1
# Workaround: the Kylin plugin needs an artifact that repo.spring.io no longer serves. See CLAUDE.md#pitfalls
RUN sed -i '/<module>plugin-kylin<\/module>/d;/<module>ranger-kylin-plugin-shim<\/module>/d' pom.xml \
    && perl -0pi -e 's#(</descriptor>)\n[ \t]*<descriptor>src/main/assembly/plugin-kylin\.xml</descriptor>#$1#g; s#\n[ \t]*<dependency>\s*<groupId>org\.apache\.ranger</groupId>\s*<artifactId>ranger-kylin-plugin(?:-shim)?</artifactId>(?:(?!</dependency>).)*</dependency>##gs' distro/pom.xml
RUN --mount=type=cache,target=/root/.m2 \
    mvn --no-transfer-progress -Dmaven.test.skip=true -DskipJSTests=true \
      -DskipEnunciate=true -Denunciate.skip=true -Drat.skip=true \
      -Pall clean package

FROM eclipse-temurin:8-jre-jammy AS ranger-base
ARG RANGER_VERSION=2.8.0
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       bc curl gettext-base libpostgresql-jdbc-java lsb-release netcat-openbsd postgresql-client procps python3 python3-pip tini \
    && rm -rf /var/lib/apt/lists/* \
    && ln -s /usr/bin/python3 /usr/bin/python \
    && groupadd --system ranger \
    && useradd --system --gid ranger --home /var/lib/ranger ranger
RUN pip3 install --no-cache-dir psycopg2-binary
COPY platform/images/ranger/render-config.sh /usr/local/bin/render-ranger-config

FROM ranger-base AS ranger-admin
ARG RANGER_VERSION=2.8.0
COPY --from=builder /src/target/ranger-${RANGER_VERSION}-admin.tar.gz /tmp/ranger-admin.tar.gz
RUN mkdir -p /opt/ranger/admin \
    && tar -xzf /tmp/ranger-admin.tar.gz --strip-components=1 -C /opt/ranger/admin \
    && rm /tmp/ranger-admin.tar.gz
COPY platform/images/ranger/admin-entrypoint.sh /usr/local/bin/ranger-entrypoint
EXPOSE 6080
ENTRYPOINT ["/usr/bin/tini", "--", "/usr/local/bin/ranger-entrypoint"]

FROM ranger-base AS ranger-usersync
ARG RANGER_VERSION=2.8.0
COPY --from=builder /src/target/ranger-${RANGER_VERSION}-usersync.tar.gz /tmp/ranger-usersync.tar.gz
RUN mkdir -p /opt/ranger/usersync \
    && tar -xzf /tmp/ranger-usersync.tar.gz --strip-components=1 -C /opt/ranger/usersync \
    && rm /tmp/ranger-usersync.tar.gz
COPY platform/images/ranger/usersync-entrypoint.sh /usr/local/bin/ranger-entrypoint
ENTRYPOINT ["/usr/bin/tini", "--", "/usr/local/bin/ranger-entrypoint"]
