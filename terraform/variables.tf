variable "project_id" {
  description = "The Google Cloud Project ID hosting the Agent, Model Armor, and Vertex AI resources."
  type        = string
}

variable "region" {
  description = "The Google Cloud region for deployment (e.g., us-central1)."
  type        = string
  default     = "us-central1"
}

variable "service_account_id" {
  description = "The service account ID for the FDA Patient Agent Runtime."
  type        = string
  default     = "fda-patient-agent-sa"
}

variable "model_armor_template_id" {
  description = "Identifier for the Google Cloud Model Armor template."
  type        = string
  default     = "fda-patient-agent-model-armor"
}

variable "dlp_template_display_name" {
  description = "Display name for the Sensitive Data Protection (Cloud DLP) de-identification template."
  type        = string
  default     = "Healthcare PHI De-identification Template"
}
