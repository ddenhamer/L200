"""Drug Information Retrieval Agent using OpenFDA MCP tools."""

from typing import Any, List, Optional
from google.adk.agents import LlmAgent
from ..prompts import DRUG_INFO_PROMPT
from ..tools import search_fda_drug_label, get_openfda_mcp_toolset


def create_drug_info_agent(
    model: str = "gemini-flash-latest",
    use_mcp: bool = False,
    custom_tools: Optional[List[Any]] = None,
) -> LlmAgent:
    """Create the FDA Drug Information Retrieval Agent.

    Args:
        model: Gemini model identifier.
        use_mcp: Whether to attach the live OpenFDA MCPToolset.
        custom_tools: Optional custom tools list (overrides default tools if provided).

    Returns:
        LlmAgent configured for drug information retrieval with output_key='drug_info'.
    """
    if custom_tools is not None:
        tools = custom_tools
    elif use_mcp:
        tools = [get_openfda_mcp_toolset()]
    else:
        # Default fallback tool for offline/testing and sandbox environments
        tools = [search_fda_drug_label]

    return LlmAgent(
        name="drug_info_retriever",
        model=model,
        description=(
            "Retrieves verified FDA product labeling, warnings, side effects, and indications "
            "for prescription and over-the-counter drugs using openFDA."
        ),
        instruction=DRUG_INFO_PROMPT,
        tools=tools,
        output_key="drug_info",
    )
