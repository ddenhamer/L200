"""Patient Translation Agent for converting FDA drug information to CEFR B1 English."""

from google.adk.agents import LlmAgent
from ..prompts import TRANSLATOR_PROMPT


def create_translator_agent(
    model: str = "gemini-flash-latest",
) -> LlmAgent:
    """Create the Patient Translation Agent.

    Args:
        model: Gemini model identifier.

    Returns:
        LlmAgent configured for B1 plain English translation with output_key='patient_draft'.
    """
    return LlmAgent(
        name="patient_translator",
        model=model,
        description=(
            "Translates clinical FDA drug labeling into clear, accessible CEFR B1 English. "
            "Simplifies medical terminology and strictly avoids giving personal medical advice."
        ),
        instruction=TRANSLATOR_PROMPT,
        output_key="patient_draft",
    )

