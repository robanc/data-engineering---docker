#!/usr/bin/env python3
"""
06_spark_sql_big_query.py

Reads Green + Yellow taxi parquet datasets, computes a monthly revenue report,
and writes the result to BigQuery using the Spark BigQuery connector.

Key fixes:
- Always write to a fully-qualified BigQuery table: project:dataset.table
- Use coalesce() (not repartition()) to reduce output files without a shuffle
- Pass BigQuery project explicitly via .option("project", project)
- Keep indirect write method + temporaryGcsBucket
"""

from __future__ import annotations

import argparse
from typing import Optional, Tuple

from pyspark.sql import SparkSession, DataFrame
from pyspark.sql import functions as F
from pyspark.sql import types as T


# -----------------------------
# Helpers
# -----------------------------
def parse_output_table(output: str, default_project: Optional[str]) -> Tuple[str, str, str]:
    """
    Supports:
      - dataset.table
      - project:dataset.table
      - project.dataset.table

    Returns: (project, dataset, table)
    """
    out = output.strip()

    # project:dataset.table
    if ":" in out:
        project, rest = out.split(":", 1)
        if "." not in rest:
            raise ValueError(f"--output must be project:dataset.table, got: {output}")
        dataset, table = rest.split(".", 1)
        return project, dataset, table

    parts = out.split(".")
    if len(parts) == 2:
        if not default_project:
            raise ValueError(
                "--output provided as dataset.table but --project_id was empty. "
                "Provide --project_id or use project:dataset.table"
            )
        dataset, table = parts
        return default_project, dataset, table

    if len(parts) == 3:
        project, dataset, table = parts
        return project, dataset, table

    raise ValueError(
        f"--output must be dataset.table or project:dataset.table (or project.dataset.table), got: {output}"
    )


def read_dataset(spark: SparkSession, path: str, service_type: str) -> DataFrame:
    """
    Reads parquet dataset from `path` and normalizes a minimal set of columns.
    Assumes typical NYC TLC schemas.
    """
    df = spark.read.parquet(path)

    # Normalize time columns and common fields; handle both green/yellow naming patterns
    # Green uses lpep_*; Yellow uses tpep_*
    if service_type == "green":
        pickup_col = "lpep_pickup_datetime"
        dropoff_col = "lpep_dropoff_datetime"
    else:
        pickup_col = "tpep_pickup_datetime"
        dropoff_col = "tpep_dropoff_datetime"

    # Some datasets may have vendor fields as VendorID, vendor_id, etc.
    # We'll be defensive and create expected columns if missing.
    cols = set(df.columns)

    def col_or_null(name: str, dtype: T.DataType) -> F.Column:
        return F.col(name).cast(dtype) if name in cols else F.lit(None).cast(dtype)

    # Common numeric columns (may be missing or string)
    df2 = df.select(
        col_or_null(pickup_col, T.TimestampType()).alias("pickup_datetime"),
        col_or_null(dropoff_col, T.TimestampType()).alias("dropoff_datetime"),
        # Trip attributes
        col_or_null("PULocationID", T.IntegerType()).alias("pickup_location_id"),
        col_or_null("DOLocationID", T.IntegerType()).alias("dropoff_location_id"),
        col_or_null("passenger_count", T.IntegerType()).alias("passenger_count"),
        col_or_null("trip_distance", T.DoubleType()).alias("trip_distance"),
        # Money fields
        col_or_null("fare_amount", T.DoubleType()).alias("fare_amount"),
        col_or_null("tip_amount", T.DoubleType()).alias("tip_amount"),
        col_or_null("tolls_amount", T.DoubleType()).alias("tolls_amount"),
        col_or_null("total_amount", T.DoubleType()).alias("total_amount"),
    ).withColumn("service_type", F.lit(service_type))

    # Basic cleanup: require pickup time
    df2 = df2.filter(F.col("pickup_datetime").isNotNull())
    return df2


def compute_monthly_revenue(df_green: DataFrame, df_yellow: DataFrame) -> DataFrame:
    """
    Example monthly rollup:
    - revenue_month (YYYY-MM-01 date)
    - service_type
    - trips
    - revenue_total, revenue_fare, revenue_tip, revenue_tolls
    """
    df = df_green.unionByName(df_yellow, allowMissingColumns=True)

    # revenue_month as DATE (first day of month)
    df = df.withColumn("revenue_month", F.to_date(F.date_trunc("month", F.col("pickup_datetime"))))

    agg = (
        df.groupBy("revenue_month", "service_type")
        .agg(
            F.count(F.lit(1)).alias("trips"),
            F.sum(F.coalesce(F.col("total_amount"), F.lit(0.0))).alias("revenue_total"),
            F.sum(F.coalesce(F.col("fare_amount"), F.lit(0.0))).alias("revenue_fare"),
            F.sum(F.coalesce(F.col("tip_amount"), F.lit(0.0))).alias("revenue_tip"),
            F.sum(F.coalesce(F.col("tolls_amount"), F.lit(0.0))).alias("revenue_tolls"),
        )
        .orderBy("revenue_month", "service_type")
    )

    return agg


# -----------------------------
# Main
# -----------------------------
def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input_green", required=True, help="Input parquet path for green dataset (local/GCS)")
    parser.add_argument("--input_yellow", required=True, help="Input parquet path for yellow dataset (local/GCS)")

    # BigQuery
    parser.add_argument("--project_id", default="", help="Default GCP project id (used if --output is dataset.table)")
    parser.add_argument("--output", required=True, help="dataset.table OR project:dataset.table OR project.dataset.table")
    parser.add_argument("--temp_gcs_bucket", required=True, help="GCS bucket for BigQuery indirect write staging")

    # Output tuning
    parser.add_argument(
        "--write_partitions",
        type=int,
        default=1,
        help="Number of output files to write (coalesce). Use small number for stability (default: 1).",
    )
    parser.add_argument(
        "--bq_partition_field",
        default="",
        help="Optional BigQuery partition field (must exist in output DF). Example: revenue_month",
    )
    parser.add_argument(
        "--bq_cluster_fields",
        default="",
        help="Optional BigQuery clustered fields comma-separated. Example: service_type",
    )

    args = parser.parse_args()

    spark = (
        SparkSession.builder.appName("taxi-report")
        # BigQuery connector sometimes relies on these; keep them conservative.
        .config("spark.sql.shuffle.partitions", "200")
        .getOrCreate()
    )

    # Make sure Spark knows the temp bucket for BigQuery connector
    spark.conf.set("temporaryGcsBucket", args.temp_gcs_bucket)

    # Read inputs
    df_green = read_dataset(spark, args.input_green, "green")
    df_yellow = read_dataset(spark, args.input_yellow, "yellow")

    # Transform
    df_result = compute_monthly_revenue(df_green, df_yellow)

    # Reduce output files WITHOUT shuffle
    wp = int(args.write_partitions)
    if wp < 1:
        wp = 1
    df_result = df_result.coalesce(wp)

    # Resolve output
    project, dataset, table = parse_output_table(args.output, args.project_id.strip() or None)
    bq_table_fq = f"{project}:{dataset}.{table}"  # ✅ fully qualified
    bq_table_short = f"{dataset}.{table}"         # some connector paths still expect this in "table"

    # Write to BigQuery
    writer = (
        df_result.write.format("bigquery")
        .option("project", project)  # ✅ explicit project
        .option("dataset", dataset)
        .option("table", bq_table_short)  # connector expects dataset.table here
        .option("temporaryGcsBucket", args.temp_gcs_bucket)
        .option("writeMethod", "indirect")
        .mode("overwrite")
    )

    # Optional partitioning/clustering
    if args.bq_partition_field.strip():
        writer = writer.option("partitionField", args.bq_partition_field.strip())
    if args.bq_cluster_fields.strip():
        # BigQuery connector expects comma-separated field list
        writer = writer.option("clusteredFields", args.bq_cluster_fields.strip())

    # Execute
    writer.save()

    print(f"✅ Wrote {df_result.count()} rows to BigQuery table: {bq_table_fq}")

    spark.stop()


if __name__ == "__main__":
    main()