#!/usr/bin/env python3
import argparse
import os

from pyspark.sql import DataFrame, SparkSession, functions as functions


def overwrite_batch(dataframe: DataFrame, table_name: str, batch_id: str) -> None:
    spark = dataframe.sparkSession
    if spark.catalog.tableExists(table_name):
        spark.sql(f"DELETE FROM {table_name} WHERE batch_id = '{batch_id}'")
        dataframe.writeTo(table_name).append()
    else:
        dataframe.writeTo(table_name).using("iceberg").partitionedBy("batch_id").create()


def replace_legacy_table(
    spark: SparkSession, table_name: str, required_columns: set[str]
) -> None:
    if spark.catalog.tableExists(table_name):
        existing_columns = set(spark.table(table_name).columns)
        if not required_columns <= existing_columns:
            spark.sql(f"DROP TABLE {table_name} PURGE")


def replace_table(dataframe: DataFrame, table_name: str) -> None:
    spark = dataframe.sparkSession
    if spark.catalog.tableExists(table_name):
        spark.sql(f"DROP TABLE {table_name} PURGE")
    dataframe.writeTo(table_name).using("iceberg").create()


def jdbc_query(spark: SparkSession, database_url: str, query: str) -> DataFrame:
    jdbc_url = database_url.replace("postgresql://", "jdbc:postgresql://", 1)
    credentials, location = jdbc_url.removeprefix("jdbc:postgresql://").split("@", 1)
    username, password = credentials.split(":", 1)
    return (
        spark.read.format("jdbc")
        .option("url", f"jdbc:postgresql://{location}")
        .option("dbtable", f"({query}) source_query")
        .option("user", username)
        .option("password", password)
        .option("driver", "org.postgresql.Driver")
        .load()
    )


def configure_session() -> SparkSession:
    client_secret = os.environ["OIDC_PIPELINE_CLIENT_SECRET"]
    garage_key = os.environ["GARAGE_ACCESS_KEY"]
    garage_secret = os.environ["GARAGE_SECRET_KEY"]
    return (
        SparkSession.builder.appName("retail-lakehouse")
        .config("spark.sql.catalog.lakehouse.credential", f"lakehouse:{client_secret}")
        .config("spark.sql.catalog.lakehouse.client.region", "garage")
        .config("spark.sql.catalog.lakehouse.s3.endpoint", "http://garage:3900")
        .config("spark.sql.catalog.lakehouse.s3.path-style-access", "true")
        .config("spark.sql.catalog.lakehouse.s3.chunked-encoding-enabled", "false")
        .config("spark.sql.catalog.lakehouse.s3.checksum-enabled", "false")
        .config("spark.sql.catalog.lakehouse.s3.access-key-id", garage_key)
        .config("spark.sql.catalog.lakehouse.s3.secret-access-key", garage_secret)
        .config("spark.sql.iceberg.merge-schema", "true")
        .config("spark.executorEnv.AWS_REQUEST_CHECKSUM_CALCULATION", "WHEN_REQUIRED")
        .config("spark.executorEnv.AWS_RESPONSE_CHECKSUM_VALIDATION", "WHEN_REQUIRED")
        .config("spark.executorEnv.GARAGE_ACCESS_KEY", garage_key)
        .config("spark.executorEnv.GARAGE_SECRET_KEY", garage_secret)
        .getOrCreate()
    )


def process(batch_id: str, database_url: str) -> None:
    spark = configure_session()
    for namespace in ("bronze", "silver", "gold"):
        spark.sql(f"CREATE NAMESPACE IF NOT EXISTS lakehouse.{namespace}")
    # Recreate only tables left behind by an older incompatible demo schema.
    for table_name, required_columns in (
        ("lakehouse.bronze.customers", {"city", "region", "acquisition_channel"}),
        ("lakehouse.bronze.orders", {"sales_channel", "campaign_id", "delivered_at"}),
        ("lakehouse.bronze.order_items", {"product_id", "unit_cost", "discount_pct"}),
        ("lakehouse.silver.customers", {"city", "region", "acquisition_channel"}),
    ):
        replace_legacy_table(spark, table_name, required_columns)

    safe_batch_id = batch_id.replace("'", "''")
    orders = jdbc_query(
        spark, database_url, f"SELECT * FROM source.orders WHERE batch_id = '{safe_batch_id}'"
    )
    items = jdbc_query(
        spark, database_url, f"SELECT * FROM source.order_items WHERE batch_id = '{safe_batch_id}'"
    )
    customers = jdbc_query(
        spark,
        database_url,
        f"""
        SELECT DISTINCT c.*
        FROM source.customers c
        JOIN source.orders o ON o.customer_id = c.customer_id
        WHERE o.batch_id = '{safe_batch_id}'
        """,
    )
    products = jdbc_query(
        spark,
        database_url,
        f"""
        SELECT DISTINCT p.*
        FROM source.products p
        JOIN source.order_items i ON i.product_id = p.product_id
        WHERE i.batch_id = '{safe_batch_id}'
        """,
    )
    campaigns = jdbc_query(spark, database_url, "SELECT * FROM source.campaigns")
    if orders.rdd.isEmpty():
        raise RuntimeError(f"No source orders found for batch {batch_id}")

    # Reference snapshots inherit the order batch so retries can replace them safely.
    customer_snapshot = customers.drop("batch_id").withColumn(
        "batch_id", functions.lit(batch_id)
    )
    product_snapshot = products.withColumn("batch_id", functions.lit(batch_id))
    campaign_snapshot = campaigns.withColumn("batch_id", functions.lit(batch_id))
    overwrite_batch(customer_snapshot, "lakehouse.bronze.customers", batch_id)
    overwrite_batch(product_snapshot, "lakehouse.bronze.products", batch_id)
    overwrite_batch(campaign_snapshot, "lakehouse.bronze.campaigns", batch_id)
    overwrite_batch(orders, "lakehouse.bronze.orders", batch_id)
    overwrite_batch(items, "lakehouse.bronze.order_items", batch_id)

    clean_customers = customer_snapshot.dropDuplicates(["batch_id", "customer_id"])
    clean_products = product_snapshot.dropDuplicates(["batch_id", "product_id"])
    order_lines = (
        items.alias("i")
        .join(orders.alias("o"), ["batch_id", "order_id"], "inner")
        .join(clean_customers.alias("c"), ["batch_id", "customer_id"], "inner")
        .join(clean_products.alias("p"), ["batch_id", "product_id"], "inner")
        .join(campaign_snapshot.alias("m"), ["batch_id", "campaign_id"], "left")
        .select(
            "batch_id",
            "order_id",
            "order_item_id",
            "customer_id",
            "product_id",
            functions.to_date("ordered_at").alias("order_date"),
            "ordered_at",
            "shipped_at",
            "delivered_at",
            "status",
            "currency",
            "sales_channel",
            "payment_method",
            "campaign_id",
            "campaign_name",
            "full_name",
            "email",
            "country",
            "city",
            "region",
            "customer_segment",
            "acquisition_channel",
            functions.col("p.sku").alias("sku"),
            functions.col("p.product_name").alias("product_name"),
            functions.col("p.category").alias("category"),
            functions.col("p.subcategory").alias("subcategory"),
            functions.col("p.brand").alias("brand"),
            functions.col("i.quantity").alias("quantity"),
            functions.col("i.unit_price").alias("unit_price"),
            functions.col("i.unit_cost").alias("unit_cost"),
            functions.col("i.discount_pct").alias("discount_pct"),
        )
        .withColumn(
            "gross_sales",
            (functions.col("quantity") * functions.col("unit_price")).cast("decimal(18,2)"),
        )
        .withColumn(
            "discount_amount",
            (functions.col("gross_sales") * functions.col("discount_pct")).cast("decimal(18,2)"),
        )
        .withColumn(
            "line_value",
            (functions.col("gross_sales") - functions.col("discount_amount")).cast("decimal(18,2)"),
        )
        .withColumn(
            "revenue",
            functions.when(
                functions.col("status").isin("cancelled", "refunded"), functions.lit(0)
            ).otherwise(functions.col("line_value")).cast("decimal(18,2)"),
        )
        .withColumn(
            "refund_amount",
            functions.when(
                functions.col("status") == "refunded", functions.col("line_value")
            ).otherwise(functions.lit(0)).cast("decimal(18,2)"),
        )
        .withColumn(
            "cost_of_goods",
            functions.when(
                functions.col("status").isin("cancelled", "refunded"), functions.lit(0)
            ).otherwise(functions.col("quantity") * functions.col("unit_cost")).cast("decimal(18,2)"),
        )
        .withColumn(
            "gross_profit",
            (functions.col("revenue") - functions.col("cost_of_goods")).cast("decimal(18,2)"),
        )
        .withColumn(
            "fulfillment_days",
            functions.when(
                functions.col("delivered_at").isNotNull(),
                functions.datediff("delivered_at", "ordered_at"),
            ),
        )
    )
    overwrite_batch(clean_customers, "lakehouse.silver.customers", batch_id)
    overwrite_batch(clean_products, "lakehouse.silver.products", batch_id)
    overwrite_batch(order_lines, "lakehouse.silver.order_lines", batch_id)

    sales_performance = order_lines.select(
        "batch_id", "order_date", "order_id", "order_item_id", "customer_id",
        "product_id", "country", "city", "region", "customer_segment",
        "acquisition_channel", "sales_channel", "payment_method", "campaign_name",
        "status", "sku", "product_name", "category", "subcategory", "brand",
        "quantity", "gross_sales", "discount_amount", "revenue", "refund_amount",
        "cost_of_goods", "gross_profit", "fulfillment_days",
    )
    product_performance = order_lines.groupBy(
        "batch_id", "order_date", "product_id", "sku", "product_name",
        "category", "subcategory", "brand", "sales_channel",
    ).agg(
        functions.sum("revenue").cast("decimal(18,2)").alias("revenue"),
        functions.sum("gross_profit").cast("decimal(18,2)").alias("gross_profit"),
        functions.sum("discount_amount").cast("decimal(18,2)").alias("discount_amount"),
        functions.sum("quantity").alias("units_sold"),
        functions.countDistinct("order_id").alias("order_count"),
    )
    # Lifetime metrics span every batch, so customer_360 is rebuilt in full.
    all_order_lines = spark.table("lakehouse.silver.order_lines")
    customer_360 = all_order_lines.groupBy(
        "customer_id", "full_name", "email", "country", "city",
        "region", "customer_segment", "acquisition_channel",
    ).agg(
        functions.min("order_date").alias("first_order_date"),
        functions.max("order_date").alias("last_order_date"),
        functions.sum("revenue").cast("decimal(18,2)").alias("lifetime_value"),
        functions.sum("gross_profit").cast("decimal(18,2)").alias("gross_profit"),
        functions.countDistinct("order_id").alias("order_count"),
        functions.sum("quantity").alias("units_purchased"),
        functions.sum("refund_amount").cast("decimal(18,2)").alias("refund_amount"),
    ).withColumn(
        "is_repeat_customer", functions.col("order_count") > 1
    )

    overwrite_batch(sales_performance, "lakehouse.gold.sales_performance", batch_id)
    overwrite_batch(product_performance, "lakehouse.gold.product_performance", batch_id)
    replace_table(customer_360, "lakehouse.gold.customer_360")

    # Reject invalid gold output before the semantic layer can expose it.
    if sales_performance.filter(functions.col("gross_profit") > functions.col("revenue")).count():
        raise RuntimeError("Quality check failed: gross profit exceeds revenue")
    if sales_performance.filter(
        (functions.col("fulfillment_days") < 0)
        | (functions.col("discount_amount") < 0)
        | (functions.col("revenue") < 0)
    ).count():
        raise RuntimeError("Quality check failed: invalid fulfillment or monetary values")
    if sales_performance.select("order_item_id").distinct().count() != sales_performance.count():
        raise RuntimeError("Quality check failed: duplicate order lines")
    if any(table.rdd.isEmpty() for table in (sales_performance, product_performance, customer_360)):
        raise RuntimeError("Quality check failed: empty gold output")
    spark.stop()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-id", required=True)
    parser.add_argument("--database-url", default=os.environ.get("AIRFLOW_CONN_RETAIL_SOURCE"))
    args = parser.parse_args()
    if not args.database_url:
        parser.error("AIRFLOW_CONN_RETAIL_SOURCE is required")
    process(args.batch_id, args.database_url)


if __name__ == "__main__":
    main()
