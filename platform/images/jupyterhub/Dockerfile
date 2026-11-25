FROM maven:3.9.11-eclipse-temurin-17 AS dependencies

ARG ICEBERG_VERSION=1.10.0
WORKDIR /deps
RUN mvn dependency:copy \
      -Dartifact=org.apache.iceberg:iceberg-spark-runtime-3.5_2.12:${ICEBERG_VERSION} \
      -DoutputDirectory=/deps \
    && mvn dependency:copy \
      -Dartifact=org.apache.iceberg:iceberg-aws-bundle:${ICEBERG_VERSION} \
      -DoutputDirectory=/deps

FROM quay.io/jupyterhub/jupyterhub:5.3.0

RUN apt-get update \
    && apt-get install -y --no-install-recommends -o Acquire::Retries=5 curl openjdk-17-jre-headless \
    && rm -rf /var/lib/apt/lists/* \
    && python3 -m pip install --no-cache-dir \
        oauthenticator==17.3.0 \
        jupyterlab==4.4.9 \
        notebook==7.4.7 \
        trino==0.336.0 \
        "pyiceberg[s3fs,pyarrow]==0.10.0" \
        pandas==2.3.3 \
        requests==2.32.5 \
        pyspark==3.5.8

COPY --from=dependencies /deps/*.jar /tmp/jars/
RUN cp /tmp/jars/*.jar "$(python3 -c 'import pyspark; print(pyspark.__path__[0])')/jars/" \
    && rm -rf /tmp/jars

ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64

CMD ["jupyterhub", "-f", "/srv/jupyterhub/jupyterhub_config.py"]
