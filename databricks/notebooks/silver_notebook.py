# Databricks notebook source
from pyspark.sql import SparkSession
spark = SparkSession.builder.getOrCreate()

df = spark.read.table("suppliers_catalog.bronze.supplier_orders")

# COMMAND ----------

display(df.limit(5))

# COMMAND ----------

## checking naming and datatypes

df.columns

# COMMAND ----------

df.dtypes

# COMMAND ----------

from pyspark.sql import functions as F
# adjust data types 
df = df.withColumn("order_date", F.to_date("order_date", "dd.MM.yyyy"))
df = df.withColumn("promised_delivery_date", F.to_date("promised_delivery_date", "dd.MM.yyyy"))
df = df.withColumn("actual_delivery_date", F.to_date("actual_delivery_date", "dd.MM.yyyy"))

# COMMAND ----------

## checking for null values
df.select([
    F.count(F.when(F.col(c).isNull(), 1)).alias(c)
    for c in df.columns
]).display()

# COMMAND ----------

## so we would assume that the null values represent order that are still in progress (not delivered yet)

# COMMAND ----------

df.dtypes

# COMMAND ----------

# listing order statuses 
df.select("order_status").distinct().display()

# COMMAND ----------

# listin lead reasons
df.select("lead_reason").distinct().display()

# COMMAND ----------

# time ranges 
print("min_date: ", df.agg(F.min("order_date")).collect()[0][0])
print("max_date: ", df.agg(F.max("order_date")).collect()[0][0])

# COMMAND ----------

# number of buyers
print("number of buyers in this dataset is : ", df.select("buyer_id").distinct().count())

# COMMAND ----------

# number of suppliers & nr of items ordered
print("number of suppliers: ", df.select("supplier_id").distinct().count())
print("number of items ordered: ", df.select("item_id").distinct().count())

# COMMAND ----------

## EDA (ideas)
## suppliers with the shorest time (from purchase to delivery)
## top ten suppliers with highest/lowest promised lead time
## top ten suppliers with highest/lowest actual delivery days
## top ten suppliers with highest/lowest lead time variance
## top ten suppliers with highest/lowest quantities delivered and ordered
## suppliers with highest/lowest on_time_delivery
## suppliers with the most/least (delivered) status and most/least (cancelled) order status

# COMMAND ----------

## suppliers with the shorest time (from purchase to delivery)
r = (
    df
    .withColumn("delivery_diff_days", F.datediff("actual_delivery_date", "promised_delivery_date"))
    .filter(F.col("delivery_diff_days").isNotNull())
    .select("supplier_name", "promised_delivery_date", "actual_delivery_date", "delivery_diff_days")
    .orderBy("delivery_diff_days")
)
r.display()

# COMMAND ----------

## shorest, highest and avg delivery time (excluding any negative values)
r_positive = r.filter(F.col("delivery_diff_days") > 0)
r_positive.select(
    F.min("delivery_diff_days").alias("min"),
    F.max("delivery_diff_days").alias("max"),
    F.avg("delivery_diff_days").alias("avg")
).show()

# COMMAND ----------

# shorest delivery time and the supplier name 
top10_min = (
    r_positive
    .groupBy("supplier_name")
    .agg(F.min("delivery_diff_days").alias("lowest_diff"))
    .orderBy("lowest_diff")
    .limit(10)
).display()

# COMMAND ----------

# longest delivery time and the supplier name 
top10_max = (
    r_positive
    .groupBy("supplier_name")
    .agg(F.max("delivery_diff_days").alias("worst_diff"))
    .orderBy(F.desc("worst_diff"))
    .limit(10)
).display()

# COMMAND ----------

# average delivery diff for each supplier
average_delivery_time_per_supplier = (
    r_positive
    .groupBy("supplier_name")
    .agg(F.avg("delivery_diff_days").alias("avg_diff"))
    .orderBy("avg_diff").withColumn("avg_diff", F.round("avg_diff"))
)
average_delivery_time_per_supplier.display()

# COMMAND ----------

pdf = average_delivery_time_per_supplier.toPandas()

pdf.plot(
    x="supplier_name",
    y="avg_diff",
    kind="bar",
    figsize=(10,5)
)

# COMMAND ----------

## suppliers with highest/lowest on_time_delivery 
r1 = (
    df
    .filter(F.col("on_time_delivery") == True)
    .groupBy("supplier_name")
    .agg(F.count("*").alias("on_time_count"))
    .orderBy(F.desc("on_time_count"))
)
r1.display()

# COMMAND ----------

## order status delivered
r2 = (
    df
    .filter(F.col("order_status") == "delivered")
    .groupBy("supplier_name")
    .agg(F.count("*").alias("delivered_count"))
    .orderBy(F.desc("delivered_count"))
).display()

# COMMAND ----------

## order status (cancelled)
r3 = (
    df
    .filter(F.col("order_status") == "cancelled")
    .groupBy("supplier_name")
    .agg(F.count("*").alias("cancelled_count"))
    .orderBy(F.desc("cancelled_count"))
).display()

# COMMAND ----------

normalized_df = df.withColumn(
    "on_time_flag",
    F.when(F.lower("on_time_delivery") == "true", 1.0)
     .when(F.lower("on_time_delivery") == "false", 0.0)
     .otherwise(None) # for in progress & cancelled orders
)

# feature prep
features = (
    normalized_df.groupBy("supplier_id", "supplier_name")
    .agg(
        F.count("*").alias("total_orders"),
        F.avg("on_time_flag").alias("on_time_rate"), # fraction of orders delivered on time 
        F.avg("lead_time_variance_days").alias("avg_lead_variance"),
        F.stddev("lead_time_variance_days").alias("lead_variance_std"), # (consistency) / low = predictable
        F.avg(
            F.col("quantity_received") / F.col("quantity_ordered")
        ).alias("fill_rate"),
        F.avg(
            F.when(F.col("order_status") == "cancelled", 1.0).otherwise(0.0)
        ).alias("cancel_rate"), # fraction of cancelled orders
    ).fillna(0)
)

# COMMAND ----------

features.display()

# COMMAND ----------

from pyspark.sql import Window

def minmax(df, col, higher_is_better=True):
    lo = df.agg(F.min(col)).first()[0]
    hi = df.agg(F.max(col)).first()[0]
    rng = (hi - lo) or 1.0
    norm = (F.col(col) - F.lit(lo)) / F.lit(rng) # (value-min)/range
    if not higher_is_better:
        norm = 1 - norm
    return df.withColumn(col + "_n", norm) # e.g. on_time_rate_n i.e. a new column

# COMMAND ----------

f = features
f = minmax(f, "on_time_rate", higher_is_better=True)
f = minmax(f, "avg_lead_variance", higher_is_better=False)
f = minmax(f, "lead_variance_std", higher_is_better=False)
f = minmax(f, "fill_rate", higher_is_better=True)
f = minmax(f, "cancel_rate", higher_is_better=False)

# COMMAND ----------

# printing normalized values
display(f.select("supplier_id", *list(W.keys())))

# COMMAND ----------

# weights
W = {
    "on_time_rate_n": 0.35,
    "avg_lead_variance_n": 0.25,
    "lead_variance_std_n": 0.15,
    "fill_rate_n": 0.15,
    "cancel_rate_n": 0.10
}

score_expr = sum(F.col(c) * F.lit(w) for c, w in W.items())
gold = f.withColumn("supplier_index", F.round(score_expr * 100, 1))

for c, w in W.items():
    gold = gold.withColumn("f_" + c, F.round(F.col(c) * F.lit(w) * 100, 1))

serving_table = gold.select(
    "supplier_id", "supplier_name", "supplier_index", "total_orders",
    *[F.col("f_" + c).alias(c.replace("_n", "_pts")) for c in W]
)

serving_table.display()

# COMMAND ----------

serving_table.write.mode("overwrite").saveAsTable("suppliers_catalog.gold.supplier_index")

# COMMAND ----------

