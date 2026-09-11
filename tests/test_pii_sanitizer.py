"""Unit tests for Model Armor & Cloud DLP PII Redaction Guardrail Plugin."""

import os
import sys
import pytest

workspace_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
venv_libs = os.path.join(workspace_dir, ".venv_libs")
if venv_libs not in sys.path:
    sys.path.insert(0, venv_libs)
if workspace_dir not in sys.path:
    sys.path.insert(0, workspace_dir)

from google.genai import types
from google.adk.models.llm_request import LlmRequest
from fda_patient_agent.guardrails.pii_plugin import (
    ModelArmorPiiPlugin,
    sanitize_phi_text,
)
from fda_patient_agent.agent import app


def test_sanitize_ssn():
    """Verify SSN detection and replacement with [US_SSN]."""
    raw_text = "My SSN is 123-45-6789. Can I take Metformin?"
    sanitized, count = sanitize_phi_text(raw_text)
    assert count == 1
    assert "123-45-6789" not in sanitized
    assert "[US_SSN]" in sanitized
    assert "Can I take Metformin?" in sanitized


def test_sanitize_phone_and_email():
    """Verify phone and email redaction."""
    raw_text = "Please reach me at 555-123-4567 or patient.jane@example.com about ibuprofen."
    sanitized, count = sanitize_phi_text(raw_text)
    assert count == 2
    assert "555-123-4567" not in sanitized
    assert "patient.jane@example.com" not in sanitized
    assert "[PHONE_NUMBER]" in sanitized
    assert "[EMAIL_ADDRESS]" in sanitized


def test_sanitize_dob_and_mrn():
    """Verify Date of Birth and Medical Record Number redaction."""
    raw_text = "Patient MRN: A892104, born 04/15/1975. Question about Lisinopril."
    sanitized, count = sanitize_phi_text(raw_text)
    assert count >= 2
    assert "A892104" not in sanitized
    assert "04/15/1975" not in sanitized
    assert "[MEDICAL_RECORD_NUMBER]" in sanitized
    assert "[DATE_OF_BIRTH]" in sanitized


def test_sanitize_patient_name_intro():
    """Verify patient name introduction pattern redaction."""
    raw_text = "Hello, my name is John Smith and I was prescribed lisinopril."
    sanitized, count = sanitize_phi_text(raw_text)
    assert count == 1
    assert "John Smith" not in sanitized
    assert "[PERSON_NAME]" in sanitized
    assert "lisinopril" in sanitized


def test_semantic_preservation_for_clinical_query():
    """Verify medical question and drug terms remain completely intact."""
    raw_text = (
        "Hi, I am Sarah Connor (DOB: 11/28/1984, phone: 212-555-0199). "
        "Can I take ibuprofen 400mg if I have asthma?"
    )
    sanitized, count = sanitize_phi_text(raw_text)
    assert count >= 3
    # Personal identifiers scrubbed
    assert "Sarah Connor" not in sanitized
    assert "11/28/1984" not in sanitized
    assert "212-555-0199" not in sanitized
    # Medical context preserved
    assert "ibuprofen 400mg" in sanitized
    assert "asthma" in sanitized


@pytest.mark.asyncio
async def test_plugin_on_user_message_callback():
    """Verify plugin intercepts incoming types.Content and sanitizes in-place."""
    plugin = ModelArmorPiiPlugin()
    user_message = types.Content(
        role="user",
        parts=[
            types.Part.from_text(
                text="My name is Robert Frost, SSN 999-88-7777. What are metformin side effects?"
            )
        ],
    )

    result = await plugin.on_user_message_callback(
        invocation_context=None,
        user_message=user_message,
    )

    assert result is not None
    scrubbed_text = result.parts[0].text
    assert "Robert Frost" not in scrubbed_text
    assert "999-88-7777" not in scrubbed_text
    assert "[PERSON_NAME]" in scrubbed_text
    assert "[US_SSN]" in scrubbed_text
    assert "metformin" in scrubbed_text


@pytest.mark.asyncio
async def test_plugin_before_model_callback():
    """Verify plugin scrubs prompts in LlmRequest contents before Gemini call."""
    plugin = ModelArmorPiiPlugin()
    llm_request = LlmRequest(
        model="gemini-flash-latest",
        contents=[
            types.Content(
                role="user",
                parts=[
                    types.Part.from_text(text="Patient email is patient@health.org, call 415-555-9000.")
                ],
            )
        ],
    )

    await plugin.before_model_callback(
        callback_context=None,
        llm_request=llm_request,
    )

    scrubbed_text = llm_request.contents[0].parts[0].text
    assert "patient@health.org" not in scrubbed_text
    assert "415-555-9000" not in scrubbed_text
    assert "[EMAIL_ADDRESS]" in scrubbed_text
    assert "[PHONE_NUMBER]" in scrubbed_text


def test_app_registers_pii_plugin():
    """Verify App object in agent.py includes ModelArmorPiiPlugin."""
    assert app.plugins is not None
    assert len(app.plugins) >= 1
    plugin_names = [p.name for p in app.plugins]
    assert "model_armor_pii_plugin" in plugin_names

