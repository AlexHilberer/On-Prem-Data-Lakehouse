FROM maven:3.9.11-eclipse-temurin-17 AS dependencies

ARG ICEBERG_VERSION=1.10.0
WORKDIR /deps
RUN mvn dependency:copy \
      -Dartifact=org.apache.iceberg:iceberg-spark-runtime-3.5_2.12:${ICEBERG_VERSION} \
      -DoutputDirectory=/deps \
    && mvn dependency:copy \
      -Dartifact=org.apache.iceberg:iceberg-aws-bundle:${ICEBERG_VERSION} \
      -DoutputDirectory=/deps \
    && mvn dependency:copy \
      -Dartifact=org.postgresql:postgresql:42.7.7 \
      -DoutputDirectory=/deps

FROM apache/spark:3.5.8-java17-python3
USER root
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*
COPY --from=dependencies /deps/*.jar /opt/spark/jars/
COPY data-pipeline/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
USER spark
