# Databricks notebook source
# MAGIC %sql 
# MAGIC create catalog if not exists suppliers_catalog;

# COMMAND ----------

# MAGIC %sql
# MAGIC create schema if not exists suppliers_catalog.bronze;
# MAGIC create schema if not exists suppliers_catalog.silver;
# MAGIC create schema if not exists suppliers_catalog.gold;

# COMMAND ----------

