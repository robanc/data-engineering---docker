output "project_id" {
  value = var.project_id
}

output "bucket_name" {
  value = google_storage_bucket.data_lake.name
}

output "dataset_id" {
  value = google_bigquery_dataset.stackoverflow_dataset.dataset_id
}
