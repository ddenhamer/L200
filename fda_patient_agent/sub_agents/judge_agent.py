"""LLM-as-a-Judge Reviewer Agent for approval gating and reflection loops."""

from typing import Any, List, Optional
from google.adk.agents import LlmAgent
from ..prompts import JUDGE_PROMPT
from ..tools import approve_patient_response, reject_patient_response


def create_judge_agent(
    model: str = "gemini-flash-latest",
    custom_tools: Optional[List[Any]] = None,
) -> LlmAgent:
    """Create the LLM-as-a-Judge Reviewer Agent.

    Args:
        model: Gemini model identifier.
        custom_tools: Optional custom tools list (defaults to approve_patient_response and reject_patient_response).

    Returns:
        LlmAgent configured to evaluate B1 language and lack of medical advice.
    """
    tools = custom_tools if custom_tools is not None else [
        approve_patient_response,
        reject_patient_response,
    ]

    return LlmAgent(
        name="llm_judge",
        model=model,
        description=(
            "Evaluates drafts for patient-friendly CEFR B1 English and ensures strict absence of "
            "prescriptive medical advice. Calls approval or rejection tools to control loop execution."
        ),
        instruction=JUDGE_PROMPT,
        tools=tools,
    )

