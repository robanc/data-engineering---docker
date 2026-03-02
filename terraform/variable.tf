variable "location" {
  description = "Project Location"
  default     = "US"
}

variable "bq_dataset_name" {
  description = "My BigQuery Dataset Name"
  default     = "demo_dataset"
}

variable "gcs_storage_class" {
  description = "Bucket Storage Class"
  default     = "STANDARD"
}

variable "gcs_bucket_name" {
  description = "My Storage Bucket Name"
  default     = "project-6292d04f-07f5-426b-ad4-terra-bucket"
}

variable "project" {
  description = "Project"
  default     = "project-6292d04f-07f5-426b-ad4"
}

variable "region" {
  description = "Region"
  default     = "us-central1"
}
