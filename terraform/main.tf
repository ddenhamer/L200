terraform {
  required_version = ">= 1.5.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">= 5.30.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# ==============================================================================
# 1. Enable Required Google Cloud APIs
# ==============================================================================
resource "google_project_service" "enabled_apis" {
  for_each = toset([
    "aiplatform.googleapis.com",    # Vertex AI & Agent Engine
    "dlp.googleapis.com",           # Sensitive Data Protection (Cloud DLP)
    "modelarmor.googleapis.com",    # Model Armor LLM Guardrails
    "cloudtrace.googleapis.com",    # OpenTelemetry Cloud Trace
    "telemetry.googleapis.com",     # Google Cloud Telemetry API (OTLP trace ingestion)
    "logging.googleapis.com",       # Cloud Logging (Structured JSON logs)
    "secretmanager.googleapis.com", # Secret Manager for API Keys
  ])

  project            = var.project_id
  service            = each.key
  disable_on_destroy = false
}

# ==============================================================================
# 2. IAM Service Account & Minimal Least-Privilege Permissions
# ==============================================================================
resource "google_service_account" "agent_runtime_sa" {
  account_id   = var.service_account_id
  display_name = "FDA Patient Agent Runtime Service Account"
  description  = "Dedicated identity running the FDA Patient Advocate agent on Agent Runtime"
  depends_on   = [google_project_service.enabled_apis]
}

# Grant Agent Runtime role to invoke Vertex AI models and maintain sessions
resource "google_project_iam_member" "vertex_ai_user" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.agent_runtime_sa.email}"
}

# Grant Sensitive Data Protection role to inspect & de-identify PII/PHI
resource "google_project_iam_member" "dlp_user" {
  project = var.project_id
  role    = "roles/dlp.user"
  member  = "serviceAccount:${google_service_account.agent_runtime_sa.email}"
}

# Grant Cloud Trace Agent role to publish OpenTelemetry spans
resource "google_project_iam_member" "trace_agent" {
  project = var.project_id
  role    = "roles/cloudtrace.agent"
  member  = "serviceAccount:${google_service_account.agent_runtime_sa.email}"
}

# Grant Logging Log Writer role to emit structured JSON logs
resource "google_project_iam_member" "log_writer" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.agent_runtime_sa.email}"
}

# ==============================================================================
# 3. Cloud Sensitive Data Protection (DLP) - De-identification Template
# ==============================================================================
resource "google_data_loss_prevention_deidentify_template" "phi_deidentify_template" {
  parent       = "projects/${var.project_id}/locations/${var.region}"
  display_name = var.dlp_template_display_name
  description  = "Redacts healthcare PHI into semantic token tags for FDA Patient Agent"
  depends_on   = [google_project_service.enabled_apis]

  deidentify_config {
    info_type_transformations {
      transformations {
        info_types {
          name = "PERSON_NAME"
        }
        info_types {
          name = "US_SOCIAL_SECURITY_NUMBER"
        }
        info_types {
          name = "PHONE_NUMBER"
        }
        info_types {
          name = "EMAIL_ADDRESS"
        }
        info_types {
          name = "DATE_OF_BIRTH"
        }
        info_types {
          name = "US_HEALTHCARE_NPI"
        }

        primitive_transformation {
          # Replaces matching sensitive data with token like [PERSON_NAME], [DATE_OF_BIRTH]
          replace_with_info_type_config = true
        }
      }
    }
  }
}

# ==============================================================================
# 4. Google Cloud Model Armor Template
# ==============================================================================
resource "google_model_armor_template" "patient_agent_armor" {
  template_id = var.model_armor_template_id
  location    = var.region
  depends_on  = [google_project_service.enabled_apis]

  filter_config {
    # Advanced Sensitive Data Protection linking Cloud DLP de-identification
    sdp_settings {
      advanced_config {
        deidentify_template = google_data_loss_prevention_deidentify_template.phi_deidentify_template.id
      }
    }

    # Prompt Injection & Jailbreak Defense
    pi_and_jailbreak_filter_settings {
      filter_enforcement = "ENABLED"
      confidence_level   = "MEDIUM_AND_ABOVE"
    }

    # Malicious URI and safety filters
    malicious_uris_filter_settings {
      filter_enforcement = "ENABLED"
    }
  }
}
