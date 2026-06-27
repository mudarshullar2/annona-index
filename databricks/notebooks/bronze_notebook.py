# Databricks notebook source
df = (spark.read.format("parquet").option("inferSchema", True).load("abfss://landing-zone@lakehouseadlsms01.dfs.core.windows.net/"))
df.write.format("delta").mode("overwrite").saveAsTable("suppliers_catalog.bronze.supplier_orders")

# COMMAND ----------

