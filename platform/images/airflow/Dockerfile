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

FROM apache/spark:3.5.8-java17-python3 AS spark

FROM apache/airflow:3.3.0-python3.10
USER root
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl jq openjdk-17-jre-headless \
    && rm -rf /var/lib/apt/lists/*
COPY --from=spark /opt/spark /opt/spark
COPY --from=dependencies /deps/*.jar /opt/spark/jars/
ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
ENV SPARK_HOME=/opt/spark
ENV PATH=/opt/spark/bin:${PATH}
USER airflow
RUN pip install --no-cache-dir \
      "apache-airflow==3.3.0" \
      "apache-airflow-providers-fab==3.7.2" \
      "psycopg2-binary==2.9.10" \
      "faker==37.5.3" \
    && pip install --no-cache-dir --no-deps \
      "apache-airflow-providers-apache-spark==5.6.0"
