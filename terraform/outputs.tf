output "service_account_email" {
  description = "The dedicated IAM service account email for the Agent Runtime."
  value       = google_service_account.agent_runtime_sa.email
}

output "model_armor_template_id" {
  description = "The ID of the configured Model Armor template for use in the Agent."
  value       = google_model_armor_template.patient_agent_armor.template_id
}

output "dlp_deidentify_template_id" {
  description = "The resource path of the Cloud DLP / SDP de-identification template."
  value       = google_data_loss_prevention_deidentify_template.phi_deidentify_template.id
}
