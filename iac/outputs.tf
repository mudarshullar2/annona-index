output "resource_group_name" {
  value = azurerm_resource_group.rg.name
}

output "storage_account_name" {
  value = azurerm_storage_account.adls.name
}

output "data_factory_name" {
  value = azurerm_data_factory.adf.name
}

output "sql_server_fqdn" {
  value = azurerm_mssql_server.sql.fully_qualified_domain_name
}

output "access_connector_id" {
  value = azurerm_databricks_access_connector.ac.id
}