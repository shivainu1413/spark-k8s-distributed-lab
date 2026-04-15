"""
ETL Pipeline - Spark on Kubernetes Demo

This PySpark program demonstrates a complete ETL workflow:

  Extract:  Read raw CSV data from MinIO (S3)
  Transform: Data cleaning + aggregation operations (triggers Shuffle)
  Load:     Write results back to MinIO (Parquet format)

Interview key points:
  - read CSV -> DataFrame (narrow dependency, no Shuffle needed)
  - filter / withColumn (narrow dependency)
  - groupBy + agg (wide dependency, triggers Shuffle! Data exchanges between Executors)
  - write Parquet (each Executor writes its own partition)
"""

from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import StructType, StructField, StringType, IntegerType, DoubleType, DateType

# ============================================================
# 1. Create SparkSession (connect to MinIO)
# ============================================================
spark = (
    SparkSession.builder
    .appName("ETL-Pipeline-Demo")
    .config("spark.hadoop.fs.s3a.endpoint", "http://minio-svc.spark-demo.svc.cluster.local:9000")
    .config("spark.hadoop.fs.s3a.access.key", "minioadmin")
    .config("spark.hadoop.fs.s3a.secret.key", "minioadmin")
    .config("spark.hadoop.fs.s3a.path.style.access", "true")
    .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
    .getOrCreate()
)

spark.sparkContext.setLogLevel("WARN")

print("=" * 60)
print("  ETL Pipeline starting execution")
print("=" * 60)

# ============================================================
# 2. Extract - Read CSV from MinIO
#
# This step is a narrow dependency:
# Each Executor independently reads its assigned partition, no cross-Executor communication
# ============================================================
print("\n[Extract] Reading sales_data.csv from MinIO...")

schema = StructType([
    StructField("order_id", IntegerType(), True),
    StructField("customer_id", StringType(), True),
    StructField("product", StringType(), True),
    StructField("category", StringType(), True),
    StructField("quantity", IntegerType(), True),
    StructField("unit_price", DoubleType(), True),
    StructField("order_date", DateType(), True),
    StructField("region", StringType(), True),
])

df_raw = (
    spark.read
    .option("header", "true")
    .schema(schema)
    .csv("s3a://spark-data/raw/")
)

raw_count = df_raw.count()
print(f"   Read {raw_count} raw records")
print(f"   Schema:")
df_raw.printSchema()

# ============================================================
# 3. Transform - Data cleaning
#
# filter and withColumn are both narrow dependencies:
# Each row is processed independently without looking at other rows
# So no Shuffle is triggered, each Executor works independently
# ============================================================
print("[Transform - Cleaning] Processing dirty data...")

# 3a. Remove records with null product or category
df_clean = df_raw.filter(
    F.col("product").isNotNull() &
    F.col("category").isNotNull() &
    F.col("region").isNotNull()
)

# 3b. Remove records with quantity <= 0 (invalid data)
df_clean = df_clean.filter(F.col("quantity") > 0)

# 3c. Add calculated column: total_amount = quantity * unit_price
df_clean = df_clean.withColumn(
    "total_amount",
    F.col("quantity") * F.col("unit_price")
)

clean_count = df_clean.count()
removed = raw_count - clean_count
print(f"   Cleaning complete: removed {removed} dirty records, {clean_count} remaining")

# ============================================================
# 4. Transform - Aggregation
#
# This is the key point! groupBy triggers Shuffle (wide dependency)
#
# Why do we need Shuffle?
#   Suppose Executor 1 has [North, South] orders
#   Executor 2 has [North, East] orders
#   To calculate total revenue for North, both Executor's North data must be in one place
#   -> Data must be transmitted over network between Executors -> This is Shuffle
# ============================================================
print("[Transform - Aggregation] Computing sales statistics by region and category...")
print("   This step triggers Shuffle - data exchanges between Executors")

# Aggregate by region + category
df_region_category = (
    df_clean
    .groupBy("region", "category")
    .agg(
        F.count("order_id").alias("order_count"),
        F.sum("total_amount").alias("total_revenue"),
        F.avg("total_amount").alias("avg_order_value"),
        F.sum("quantity").alias("total_quantity"),
    )
    .orderBy(F.desc("total_revenue"))
)

print("   Region x Category sales statistics:")
df_region_category.show(20, truncate=False)

# Aggregate by customer (another Shuffle)
print("[Transform - Aggregation] Computing customer spending ranking...")

df_customer = (
    df_clean
    .groupBy("customer_id")
    .agg(
        F.count("order_id").alias("order_count"),
        F.sum("total_amount").alias("total_spent"),
        F.countDistinct("category").alias("categories_bought"),
    )
    .orderBy(F.desc("total_spent"))
)

print("   Customer spending ranking:")
df_customer.show(10, truncate=False)

# ============================================================
# 5. Load - Write to MinIO (Parquet format)
#
# Parquet is a columnar storage format better suited for analysis than CSV:
#   - High compression ratio (typically 1/5 to 1/10 of CSV)
#   - Schema support (no need to infer column types each time)
#   - Predicate pushdown support (only read needed columns)
#
# Each Executor writes its own partition file, resulting in
# multiple .parquet files in MinIO - this is distributed write
# ============================================================
print("[Load] Writing results to MinIO (Parquet format)...")

# Write cleaned complete data
df_clean.write.mode("overwrite").parquet("s3a://spark-data/processed/clean_sales/")
print("   Cleaned data -> s3a://spark-data/processed/clean_sales/")

# Write region category statistics
df_region_category.write.mode("overwrite").parquet("s3a://spark-data/processed/region_category_stats/")
print("   Region category statistics -> s3a://spark-data/processed/region_category_stats/")

# Write customer statistics
df_customer.write.mode("overwrite").parquet("s3a://spark-data/processed/customer_stats/")
print("   Customer statistics -> s3a://spark-data/processed/customer_stats/")

# ============================================================
# 6. Verification - Read Parquet files to verify write success
# ============================================================
print("\n[Verification] Reading Parquet files to verify data correctness...")

verify_df = spark.read.parquet("s3a://spark-data/processed/region_category_stats/")
verify_count = verify_df.count()
print(f"   region_category_stats: {verify_count} records")

print("\n" + "=" * 60)
print("  ETL Pipeline execution complete!")
print("=" * 60)

spark.stop()
