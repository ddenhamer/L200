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
# 1. Cloud Sensitive Data Protection (DLP) - De-identification Template
# ==============================================================================
# Defines transformation rules that replace sensitive patient health identifiers
# with semantic labels (e.g. "John" -> "[PERSON_NAME]") so LLM retains context.
resource "google_data_loss_prevention_deidentify_template" "phi_deidentify_template" {
  parent       = "projects/${var.project_id}/locations/${var.region}"
  display_name = var.dlp_template_display_name
  description  = "Redacts healthcare PHI into semantic token tags for FDA Patient Agent"

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
# 2. Google Cloud Model Armor Template
# ==============================================================================
# Connects the DLP de-identification template with LLM guardrails (jailbreak,
# prompt injection, and harmful content filtering) for Agent Runtime.
resource "google_model_armor_template" "patient_agent_armor" {
  template_id = var.model_armor_template_id
  location    = var.region

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

