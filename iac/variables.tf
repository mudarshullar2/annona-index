variable "prefix" {
  description = "Short name prefix for all resources"
  type        = string
  default     = "lakehouse"
}

variable "location" {
  description = "Azure region for all resources"
  type        = string
  default     = "northeurope"
}

# provisioning issues while creating sql server in north/west europe
# case: https://learn.microsoft.com/en-us/answers/questions/1377749/unable-to-create-sql-db-using-free-offer
variable "sql_location" {
  type    = string
  default = "centralus"
}

variable "sql_admin_login" {
  description = "Admin username for the SQL logical server"
  type        = string
  default     = "sqladmin"
}

variable "sql_admin_password" {
  description = "Admin password for the SQL logical server"
  type        = string
  sensitive   = true
}

variable "my_ip" {
  description = "Your public IP to allow through the SQL firewall"
  type        = string
  default     = ""
}

variable "tags" {
  description = "Tags applied to every resource"
  type        = map(string)
  default = {
    project = "annona-index"
    managed = "terraform"
  }
}

variable "name_suffix" {
  description = "Short unique suffix for globally-unique resource names"
  type        = string
  default     = "ms01"
}

variable "databricks_account_id" {
  type = string
}

variable "azure_tenant_id" {
  type = string
}