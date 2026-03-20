provider "google" {
  project = var.project_id
  region  = var.region
}

locals {
  required_apis = [
    "bigquery.googleapis.com",
    "storage.googleapis.com",
    "iam.googleapis.com",
    "compute.googleapis.com"
  ]
}

resource "google_project_service" "required_apis" {
  for_each           = toset(local.required_apis)
  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}

resource "google_storage_bucket" "data_lake" {
  name                        = var.bucket_name
  location                    = var.region
  storage_class               = "STANDARD"
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"

  depends_on = [google_project_service.required_apis]
}

resource "google_bigquery_dataset" "stackoverflow_dataset" {
  dataset_id  = var.dataset_id
  project     = var.project_id
  location    = var.location
  description = "Dataset for Stack Overflow technology trends project"

  depends_on = [google_project_service.required_apis]
}
