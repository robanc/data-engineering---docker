terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "7.16.0"
    }
  }
}

provider "google" {
  project = "project-6292d04f-07f5-426b-ad4"
  region  = "us-central1"
}


resource "google_storage_bucket" "demo-bucket" {
  name          = "project-6292d04f-07f5-426b-ad4-terra-bucket"
  location      = "US"
  storage_class = "STANDARD"
  force_destroy = true

  uniform_bucket_level_access = true

  lifecycle_rule {
    action {
      type = "AbortIncompleteMultipartUpload"
    }
    condition {
      age = 1
    }
  }
}
