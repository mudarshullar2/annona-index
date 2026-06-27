# Databricks notebook source
# MAGIC %sql 
# MAGIC create catalog if not exists suppliers_catalog;

# COMMAND ----------

# MAGIC %sql
# MAGIC create schema if not exists suppliers_catalog.bronze;
# MAGIC create schema if not exists suppliers_catalog.silver;
# MAGIC create schema if not exists suppliers_catalog.gold;

# COMMAND ----------

# MAGIC %sql
# MAGIC show storage credentials;

# COMMAND ----------

# MAGIC %sql
# MAGIC -- create an external location
# MAGIC create external location if not exists landing_zone
# MAGIC url 'abfss://landing-zone@lakehouseadlsms01.dfs.core.windows.net/'
# MAGIC with (storage credential `lakehouse-dbw-connector`)

# COMMAND ----------

