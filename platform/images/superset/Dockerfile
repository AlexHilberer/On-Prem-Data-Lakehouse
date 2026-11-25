FROM python:3.10-bookworm AS dependencies

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       build-essential libldap2-dev libsasl2-dev libssl-dev \
    && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir --target /dependencies \
    "python-ldap==3.4.4" "psycopg2-binary==2.9.10" "Authlib==1.6.5"

FROM apache/superset:6.1.0
USER root
COPY --from=dependencies /dependencies /app/pythonpath
USER superset
