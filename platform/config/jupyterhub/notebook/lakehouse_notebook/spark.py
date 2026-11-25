import os
import socket

from .auth import get_token

AWS_CHECKSUM_OPTIONS = (
    "-Daws.requestChecksumCalculation=WHEN_REQUIRED "
    "-Daws.responseChecksumValidation=WHEN_REQUIRED"
)


class LakehouseSparkBuilder:
    """Pre-configured Spark builder: the catalog authenticates to Polaris as the user."""

    def __init__(self):
        self._app_name = f"notebook-{os.environ.get('JUPYTERHUB_USER', 'user')}"
        self._extra = {}

    def appName(self, name):
        self._app_name = name
        return self

    def config(self, key, value):
        self._extra[key] = value
        return self

    def getOrCreate(self):
        from pyspark.sql import SparkSession

        catalog = "spark.sql.catalog.lakehouse"
        builder = (
            SparkSession.builder.appName(self._app_name)
            .master("spark://spark-master:7077")
            .config("spark.driver.host", socket.gethostname())
            .config("spark.driver.bindAddress", "0.0.0.0")
            .config("spark.driver.memory", "512m")
            .config("spark.executor.memory", "1024m")
            .config("spark.cores.max", "2")
            .config("spark.sql.session.timeZone", "UTC")
            .config("spark.redaction.regex", "(?i)secret|password|token|access[.]?key|credential")
            .config("spark.sql.extensions", "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions")
            .config("spark.sql.defaultCatalog", "lakehouse")
            .config(catalog, "org.apache.iceberg.spark.SparkCatalog")
            .config(f"{catalog}.type", "rest")
            .config(f"{catalog}.uri", os.environ["POLARIS_URI"])
            .config(f"{catalog}.warehouse", os.environ["POLARIS_WAREHOUSE"])
            .config(f"{catalog}.rest.auth.type", "oauth2")
            .config(f"{catalog}.oauth2-server-uri", f"{os.environ['POLARIS_URI']}/v1/oauth/tokens")
            .config(f"{catalog}.token", get_token())
            .config(f"{catalog}.io-impl", "org.apache.iceberg.aws.s3.S3FileIO")
            .config(f"{catalog}.client.region", "garage")
            .config(f"{catalog}.s3.endpoint", "http://garage:3900")
            .config(f"{catalog}.s3.path-style-access", "true")
            .config(f"{catalog}.s3.chunked-encoding-enabled", "false")
            .config(f"{catalog}.s3.checksum-enabled", "false")
            .config(f"{catalog}.s3.access-key-id", os.environ["GARAGE_ACCESS_KEY"])
            .config(f"{catalog}.s3.secret-access-key", os.environ["GARAGE_SECRET_KEY"])
            .config("spark.driver.extraJavaOptions", AWS_CHECKSUM_OPTIONS)
            .config("spark.executor.extraJavaOptions", AWS_CHECKSUM_OPTIONS)
        )
        for key, value in self._extra.items():
            builder = builder.config(key, value)
        return builder.getOrCreate()
