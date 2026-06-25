terraform {
  required_version = ">= 1.5"

  required_providers {
    azurerm = {
      source = "hashicorp/azurerm"
      version = "~> 4.0"
    }
    random = {
      source = "hashicorp/random"
      version = "~> 3.6"
    }
  }
}

provider "azurerm" {
  features {}
}

# resource group
resource "azurerm_resource_group" "rg" {
  name = "${var.prefix}-rg"
  location = var.location
  tags = var.tags
}

# storage account
resource "azurerm_storage_account" "adls" {
  name = "${var.prefix}adls${var.name_suffix}"
  resource_group_name = azurerm_resource_group.rg.name
  location = azurerm_resource_group.rg.location
  account_tier = "Standard"
  account_replication_type = "LRS"
  account_kind = "StorageV2"
  is_hns_enabled = true
  tags = var.tags
}

resource "azurerm_storage_data_lake_gen2_filesystem" "landing_zone" {
  name = "landing-zone"
  storage_account_id = azurerm_storage_account.adls.id
}

resource "azurerm_storage_data_lake_gen2_filesystem" "unity_metastore" {
  name = "unity-metastore"
  storage_account_id = azurerm_storage_account.adls.id
}

# azure data factory
resource "azurerm_data_factory" "adf" {
  name = "${var.prefix}-adf-${var.name_suffix}"
  resource_group_name = azurerm_resource_group.rg.name
  location = azurerm_resource_group.rg.location

  identity {
    type = "SystemAssigned"
  }
  tags = var.tags
}

# azure SQL (logical server & database)
resource "azurerm_mssql_server" "sql" {
  name = "${var.prefix}-sql-${var.name_suffix}"
  resource_group_name = azurerm_resource_group.rg.name
  location = var.sql_location
  version = "12.0"
  administrator_login = var.sql_admin_login
  administrator_login_password = var.sql_admin_password
  minimum_tls_version = "1.2"
  tags = var.tags
}

resource "azurerm_mssql_database" "db" {
  name = "${var.prefix}-db"
  server_id = azurerm_mssql_server.sql.id
  collation = "SQL_Latin1_General_CP1_CI_AS"
  sku_name = "Basic"
  max_size_gb = 2
  tags = var.tags
}

# allowing other azure services to reach
resource "azurerm_mssql_firewall_rule" "allow_azure" {
  name             = "AllowAzureServices"
  server_id        = azurerm_mssql_server.sql.id
  start_ip_address = "0.0.0.0"
  end_ip_address   = "0.0.0.0"
}

# allowing own machine to connect
resource "azurerm_mssql_firewall_rule" "allow_my_ip" {
  count            = var.my_ip == "" ? 0 : 1
  name             = "AllowMyIP"
  server_id        = azurerm_mssql_server.sql.id
  start_ip_address = var.my_ip
  end_ip_address   = var.my_ip
}

resource "azurerm_databricks_workspace" "dbw" {
  name                = "${var.prefix}-dbw-${var.name_suffix}"
  resource_group_name = azurerm_resource_group.rg.name
  location            = var.location
  sku                 = "premium"
  tags                = var.tags
}