"""Root Agent and Application definition for the FDA Patient Drug Information System.

Configured for deployment to Google Cloud Agent Runtime with:
- Resumability and Session Memory
- OpenTelemetry Generative AI tracing
- OpenFDA MCP retrieval agent
- B1 plain English translation agent
- In-loop LLM-as-a-Judge approval gating
"""

import os
from typing import Optional

# Enable OpenTelemetry semantic conventions for Generative AI
os.environ["OTEL_SEMCONV_STABILITY_OPT_IN"] = "gen_ai_latest_experimental"
# Ensure the full message content (prompts & responses) is captured in the trace events
os.environ["OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT"] = "EVENT_ONLY"

from google.adk.agents import LoopAgent, SequentialAgent, LlmAgent
from google.adk.apps.app import App, ResumabilityConfig, EventsCompactionConfig

from .prompts import RESPONDER_PROMPT
from .sub_agents.drug_info_agent import create_drug_info_agent
from .sub_agents.translator_agent import create_translator_agent
from .sub_agents.judge_agent import create_judge_agent


def build_pipeline(
    model: str = "gemini-flash-latest",
    use_mcp: bool = True,
    max_loop_iterations: int = 3,
) -> SequentialAgent:
    """Construct the full multi-agent sequential pipeline with translation loop.

    Args:
        model: Model identifier for Gemini models.
        use_mcp: Whether to use live OpenFDA MCPToolset (True) or fallback tool (False).
        max_loop_iterations: Maximum review attempts before terminating loop.

    Returns:
        SequentialAgent coordinating drug retrieval, translation loop, and final delivery.
    """
    drug_info_agent = create_drug_info_agent(model=model, use_mcp=use_mcp)
    translator_agent = create_translator_agent(model=model)
    judge_agent = create_judge_agent(model=model)

    responder_agent = LlmAgent(
        name="patient_responder",
        model=model,
        description="Delivers the final approved patient-friendly explanation with medical disclaimer.",
        instruction=RESPONDER_PROMPT,
        output_key="final_patient_response",
    )

    translation_loop = LoopAgent(
        name="translation_review_loop",
        description="Iterative translation and LLM-as-a-Judge review loop ensuring B1 English and no medical advice.",
        sub_agents=[translator_agent, judge_agent],
        max_iterations=max_loop_iterations,
    )

    root = SequentialAgent(
        name="fda_patient_advocate",
        description=(
            "Patient advocate agent that retrieves official FDA drug labeling via openFDA, "
            "translates clinical details into accessible CEFR B1 English, and performs in-loop "
            "safety gating via an LLM judge."
        ),
        sub_agents=[
            drug_info_agent,
            translation_loop,
            responder_agent,
        ],
    )
    return root


# Determine MCP usage from environment; defaults to True (official MCP) but can be toggled
_use_mcp_env = os.getenv("USE_OPENFDA_MCP", "true").lower() in ("true", "1", "yes")

# Root agent entrypoint for ADK CLI, tests, and Agent Runtime
root_agent = build_pipeline(use_mcp=_use_mcp_env)

# App wrapper configured for Google Cloud Agent Runtime
# - ResumabilityConfig: ensures sessions survive drops and recover their state seamlessly
# - EventsCompactionConfig: compacts older events to maintain optimal context window
app = App(
    name="fda_patient_agent",
    root_agent=root_agent,
    resumability_config=ResumabilityConfig(is_resumable=True),
    events_compaction_config=EventsCompactionConfig(
        compaction_interval=5,
        overlap_size=1,
    ),
)

