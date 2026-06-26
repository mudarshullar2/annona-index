terraform {
  required_version = ">= 1.5"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
    databricks = {
      source  = "databricks/databricks"
      version = "~> 1.50"
    }
  }
}

provider "azurerm" {
  features {}
}

# Account-level Databricks provider (for Unity Catalog metastore).
# Auth flows through your `az login` session.
provider "databricks" {
  alias            = "account"
  host             = "https://accounts.azuredatabricks.net"
  account_id       = var.databricks_account_id
  auth_type        = "azure-cli"
  azure_tenant_id  = var.azure_tenant_id
}

# resource group
resource "azurerm_resource_group" "rg" {
  name     = "${var.prefix}-rg"
  location = var.location
  tags     = var.tags
}

# storage account
resource "azurerm_storage_account" "adls" {
  name                     = "${var.prefix}adls${var.name_suffix}"
  resource_group_name      = azurerm_resource_group.rg.name
  location                 = azurerm_resource_group.rg.location
  account_tier             = "Standard"
  account_replication_type = "LRS"
  account_kind             = "StorageV2"
  is_hns_enabled           = true
  tags                     = var.tags
}

resource "azurerm_storage_data_lake_gen2_filesystem" "landing_zone" {
  name               = "landing-zone"
  storage_account_id = azurerm_storage_account.adls.id
}

resource "azurerm_storage_data_lake_gen2_filesystem" "unity_metastore" {
  name               = "unity-metastore"
  storage_account_id = azurerm_storage_account.adls.id
}

# azure data factory
resource "azurerm_data_factory" "adf" {
  name                = "${var.prefix}-adf-${var.name_suffix}"
  resource_group_name = azurerm_resource_group.rg.name
  location            = azurerm_resource_group.rg.location

  identity {
    type = "SystemAssigned"
  }
  tags = var.tags
}

# azure SQL (logical server & database)
resource "azurerm_mssql_server" "sql" {
  name                         = "${var.prefix}-sql-${var.name_suffix}"
  resource_group_name          = azurerm_resource_group.rg.name
  location                     = var.sql_location
  version                      = "12.0"
  administrator_login          = var.sql_admin_login
  administrator_login_password = var.sql_admin_password
  minimum_tls_version          = "1.2"
  tags                         = var.tags
}

resource "azurerm_mssql_database" "db" {
  name        = "${var.prefix}-db"
  server_id   = azurerm_mssql_server.sql.id
  collation   = "SQL_Latin1_General_CP1_CI_AS"
  sku_name    = "Basic"
  max_size_gb = 2
  tags        = var.tags
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

# databricks Access Connector (managed identity for UC -> ADLS)
resource "azurerm_databricks_access_connector" "ac" {
  name                = "${var.prefix}-dbw-connector"
  resource_group_name = azurerm_resource_group.rg.name
  location            = var.location
  identity {
    type = "SystemAssigned"
  }
  tags = var.tags
}

# grant the connector access to the storage account
resource "azurerm_role_assignment" "ac_blob" {
  scope                = azurerm_storage_account.adls.id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = azurerm_databricks_access_connector.ac.identity[0].principal_id
}

# ---------------------------------------------------------------------------
# Unity Catalog metastore (account-level Databricks resources)
# ---------------------------------------------------------------------------

resource "databricks_metastore" "this" {
  provider     = databricks.account
  name         = "suppliers_metastore"
  region       = var.location
  storage_root = "abfss://${azurerm_storage_data_lake_gen2_filesystem.unity_metastore.name}@${azurerm_storage_account.adls.name}.dfs.core.windows.net/"

  force_destroy = true
}

# default storage credential (this is the piece that was failing in the UI)
resource "databricks_metastore_data_access" "this" {
  provider     = databricks.account
  metastore_id = databricks_metastore.this.id
  name         = azurerm_databricks_access_connector.ac.name

  azure_managed_identity {
    access_connector_id = azurerm_databricks_access_connector.ac.id
  }

  is_default = true

  # role assignment must exist before the credential can be validated
  depends_on = [azurerm_role_assignment.ac_blob]
}

# attach the workspace to the metastore
resource "databricks_metastore_assignment" "this" {
  provider     = databricks.account
  metastore_id = databricks_metastore.this.id
  workspace_id = azurerm_databricks_workspace.dbw.workspace_id
}
