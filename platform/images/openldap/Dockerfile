FROM debian:bookworm-slim AS builder

ARG OPENLDAP_VERSION=2.6.13
ARG OPENLDAP_URL=https://www.openldap.org/software/download/OpenLDAP/openldap-release/openldap-${OPENLDAP_VERSION}.tgz

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       build-essential ca-certificates curl groff-base libargon2-dev libevent-dev libltdl-dev \
       libsodium-dev libssl-dev pkg-config \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /src
RUN curl --fail --location --retry 5 "${OPENLDAP_URL}" -o openldap.tgz \
    && tar -xzf openldap.tgz --strip-components=1 \
    && ./configure \
       --prefix=/opt/openldap \
       --sysconfdir=/etc/openldap \
       --localstatedir=/var \
       --enable-slapd \
       --enable-modules \
       --enable-mdb=yes \
       --enable-memberof=mod \
       --enable-refint=mod \
       --with-tls=openssl \
       --with-cyrus-sasl=no \
    && make -j"$(nproc)" depend \
    && make -j"$(nproc)" \
    && make install

FROM debian:bookworm-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       ca-certificates libargon2-1 libevent-2.1-7 libltdl7 libsodium23 libssl3 tini \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 101 openldap \
    && useradd --system --uid 101 --gid openldap --home /var/lib/openldap openldap

COPY --from=builder /opt/openldap /opt/openldap
COPY --from=builder /etc/openldap/openldap /opt/openldap/etc/openldap
COPY platform/images/openldap/slapd.conf.template /opt/openldap/etc/openldap/slapd.conf.template
COPY platform/images/openldap/seed.ldif.template /opt/openldap/etc/openldap/seed.ldif.template
COPY platform/images/openldap/entrypoint.sh /usr/local/bin/openldap-entrypoint

ENV PATH=/opt/openldap/bin:/opt/openldap/sbin:${PATH}
EXPOSE 389 636
ENTRYPOINT ["/usr/bin/tini", "--", "/usr/local/bin/openldap-entrypoint"]
