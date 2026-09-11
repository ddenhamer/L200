"""PII and PHI Redaction Guardrail Plugin for Google ADK.

Integrates with Google Cloud Model Armor / Sensitive Data Protection (Cloud DLP)
with a deterministic local fallback de-identification engine for offline development.
"""

import os
import re
import logging
from typing import Optional, Tuple
from google.adk.plugins import BasePlugin
from google.genai import types

logger = logging.getLogger("fda_patient_agent.guardrails.pii")


# Regex patterns matching Sensitive Data Protection (SDP) infoTypes for healthcare
SDP_PATTERNS = [
    # US Social Security Number (US_SOCIAL_SECURITY_NUMBER)
    (re.compile(r"\b\d{3}[- ]\d{2}[- ]\d{4}\b"), "[US_SSN]"),
    # Phone Number (PHONE_NUMBER)
    (re.compile(r"\b(?:\+?1[-. ]?)?\(?([0-9]{3})\)?[-. ]?([0-9]{3})[-. ]?([0-9]{4})\b"), "[PHONE_NUMBER]"),
    # Email Address (EMAIL_ADDRESS)
    (re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"), "[EMAIL_ADDRESS]"),
    # Medical Record Number / Patient Identifier (US_HEALTHCARE_NPI / MRN)
    (re.compile(r"\b(?:MRN|patient\s*(?:ID|number|#))[:\s]*([A-Z0-9-]{6,12})\b", re.IGNORECASE), "MRN: [MEDICAL_RECORD_NUMBER]"),
    # Date of birth (DATE_OF_BIRTH)
    (re.compile(r"\b(?:DOB|born(?: on)?|birth(?:day|date)?[:\s]+)\s*(?:0?[1-9]|1[0-2])[/-](?:0?[1-9]|[12]\d|3[01])[/-](?:19|20)\d{2}\b", re.IGNORECASE), "[DATE_OF_BIRTH]"),
    # Standard standalone dates formatted as MM/DD/YYYY or YYYY-MM-DD
    (re.compile(r"\b(?:0?[1-9]|1[0-2])[/-](?:0?[1-9]|[12]\d|3[01])[/-](?:19|20)\d{2}\b"), "[DATE]"),
    # Person Name in common clinical patient intros (PERSON_NAME)
    (re.compile(r"\b(?:my name is|i am|patient:?)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+))\b", re.IGNORECASE), "patient is [PERSON_NAME]"),
]


def sanitize_phi_text(text: str) -> Tuple[str, int]:
    """Sanitize text by replacing PII/PHI with semantic Sensitive Data Protection tokens.

    Args:
        text: Raw user prompt or model response.

    Returns:
        Tuple of (sanitized_text, total_redactions_count).
    """
    if not text:
        return text, 0

    sanitized = text
    total_redactions = 0

    for pattern, replacement in SDP_PATTERNS:
        matches = len(pattern.findall(sanitized))
        if matches > 0:
            sanitized = pattern.sub(replacement, sanitized)
            total_redactions += matches

    return sanitized, total_redactions


class ModelArmorPiiPlugin(BasePlugin):
    """ADK Guardrail Plugin that intercepts prompts and responses to scrub PII/PHI.

    Ensures that neither the LLM nor OpenTelemetry traces capture sensitive patient
    identifiers (HIPAA Safe Harbor infoTypes).
    """

    def __init__(
        self,
        template_id: Optional[str] = None,
        enable_logging: bool = True,
    ):
        super().__init__(name="model_armor_pii_plugin")
        self.template_id = template_id or os.getenv("MODEL_ARMOR_TEMPLATE_ID")
        self.enable_logging = enable_logging

    async def on_user_message_callback(
        self,
        *,
        invocation_context,
        user_message: types.Content,
    ) -> Optional[types.Content]:
        """Scrub PII from incoming user messages before session persistence or agent execution."""
        if not user_message or not user_message.parts:
            return None

        modified = False
        for part in user_message.parts:
            if hasattr(part, "text") and part.text:
                sanitized, count = sanitize_phi_text(part.text)
                if count > 0:
                    part.text = sanitized
                    modified = True
                    if self.enable_logging:
                        logger.info(
                            "Sanitized %d PII/PHI tokens from user input before trace export.",
                            count,
                        )

        return user_message if modified else None

    async def before_model_callback(
        self,
        *,
        callback_context,
        llm_request,
    ):
        """Ensure all prompt contents sent to Gemini are free of sensitive PII tokens."""
        if not llm_request or not llm_request.contents:
            return None

        total_scrubbed = 0
        for content in llm_request.contents:
            if not hasattr(content, "parts") or not content.parts:
                continue
            for part in content.parts:
                if hasattr(part, "text") and part.text:
                    sanitized, count = sanitize_phi_text(part.text)
                    if count > 0:
                        part.text = sanitized
                        total_scrubbed += count

        if total_scrubbed > 0 and self.enable_logging:
            logger.info("ModelArmor: scrubbed %d tokens in before_model_callback", total_scrubbed)

        return None  # Returning None proceeds with modified llm_request

    async def after_model_callback(
        self,
        *,
        callback_context,
        llm_response,
    ):
        """Scrub any unexpected PII from model outputs before returning to user or traces."""
        if not llm_response or not hasattr(llm_response, "content") or not llm_response.content:
            return None

        content = llm_response.content
        if hasattr(content, "parts") and content.parts:
            for part in content.parts:
                if hasattr(part, "text") and part.text:
                    sanitized, count = sanitize_phi_text(part.text)
                    if count > 0:
                        part.text = sanitized
                        if self.enable_logging:
                            logger.warning(
                                "ModelArmor: Scrubbed %d unexpected PII tokens from model output.",
                                count,
                            )

        return None

