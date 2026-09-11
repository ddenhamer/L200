"""Unit and integration tests for FDA Patient Drug Information Agent."""

import os
import sys
import pytest

# Ensure workspace and dependencies are on sys.path
workspace_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
venv_libs = os.path.join(workspace_dir, ".venv_libs")
if venv_libs not in sys.path:
    sys.path.insert(0, venv_libs)
if workspace_dir not in sys.path:
    sys.path.insert(0, workspace_dir)

from google.adk.agents import LoopAgent, SequentialAgent, LlmAgent
from google.adk.apps.app import App
from google.adk.runners import InMemoryRunner

import fda_patient_agent
from fda_patient_agent.agent import root_agent, app, build_pipeline
from fda_patient_agent.tools import (
    search_fda_drug_label,
    approve_patient_response,
    reject_patient_response,
    get_openfda_mcp_toolset,
)


class DummyActions:
    """Mock actions object mirroring ADK EventActions."""
    def __init__(self):
        self.escalate = False


class DummyToolContext:
    """Mock tool execution context for testing tool handlers."""
    def __init__(self, state=None):
        self.state = state if state is not None else {}
        self.actions = DummyActions()


def test_root_agent_architecture():
    """Verify that root_agent has the expected pipeline structure and sub-agents."""
    assert isinstance(root_agent, SequentialAgent)
    assert root_agent.name == "fda_patient_advocate"
    assert len(root_agent.sub_agents) == 3

    # Stage 1: Retrieval
    retriever = root_agent.sub_agents[0]
    assert isinstance(retriever, LlmAgent)
    assert retriever.name == "drug_info_retriever"
    assert retriever.output_key == "drug_info"

    # Stage 2: Loop (Translator + Judge)
    loop = root_agent.sub_agents[1]
    assert isinstance(loop, LoopAgent)
    assert loop.name == "translation_review_loop"
    assert loop.max_iterations == 3
    assert len(loop.sub_agents) == 2
    assert loop.sub_agents[0].name == "patient_translator"
    assert loop.sub_agents[0].output_key == "patient_draft"
    assert loop.sub_agents[1].name == "llm_judge"

    # Stage 3: Final presentation
    responder = root_agent.sub_agents[2]
    assert isinstance(responder, LlmAgent)
    assert responder.name == "patient_responder"
    assert responder.output_key == "final_patient_response"


def test_app_configuration():
    """Verify App wrapper configuration for Agent Runtime deployment."""
    assert isinstance(app, App)
    assert app.name == "fda_patient_agent"
    assert app.root_agent is root_agent
    assert app.resumability_config is not None
    assert app.resumability_config.is_resumable is True
    assert app.events_compaction_config is not None
    assert app.events_compaction_config.compaction_interval == 5


def test_opentelemetry_env_vars():
    """Verify OpenTelemetry Generative AI tracing environment variables are active."""
    assert os.getenv("OTEL_SEMCONV_STABILITY_OPT_IN") == "gen_ai_latest_experimental"
    assert os.getenv("OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT") == "EVENT_ONLY"


def test_openfda_search_tool():
    """Verify fallback OpenFDA drug search tool returns FDA labeling data."""
    # Test metformin lookup
    metformin_result = search_fda_drug_label("Metformin")
    assert metformin_result["status"] == "success"
    assert metformin_result["found"] is True
    assert "type 2 diabetes" in metformin_result["data"]["indications"].lower()
    assert "lactic acidosis" in metformin_result["data"]["boxed_warning"].lower()

    # Test lisinopril lookup
    lisinopril_result = search_fda_drug_label("lisinopril")
    assert lisinopril_result["status"] == "success"
    assert any("cough" in s.lower() for s in lisinopril_result["data"]["adverse_reactions"])

    # Test ibuprofen lookup
    ibuprofen_result = search_fda_drug_label("ibuprofen")
    assert ibuprofen_result["status"] == "success"
    assert "asthma" in ibuprofen_result["data"]["contraindications"].lower()


def test_openfda_mcp_toolset_instantiation():
    """Verify get_openfda_mcp_toolset properly configures StdioConnectionParams."""
    toolset = get_openfda_mcp_toolset(
        command="npx",
        args=["-y", "@cyanheads/openfda-mcp-server@latest"],
    )
    assert toolset is not None
    assert hasattr(toolset, "connection_params")
    assert toolset.connection_params.server_params.command == "npx"
    assert toolset.connection_params.server_params.args == ["-y", "@cyanheads/openfda-mcp-server@latest"]


def test_judge_approval_tool_escalation():
    """Verify approve_patient_response sets escalate=True and stores approval."""
    ctx = DummyToolContext(state={"patient_draft": "Lisinopril is for high blood pressure. Talk to your doctor."})
    result = approve_patient_response(
        feedback="Meets CEFR B1 level and contains no medical advice.",
        tool_context=ctx,
    )

    assert result["status"] == "approved"
    assert ctx.actions.escalate is True
    assert ctx.state["approved"] is True
    assert ctx.state["final_response"] == "Lisinopril is for high blood pressure. Talk to your doctor."
    assert "Meets CEFR B1" in ctx.state["judge_feedback"]


def test_judge_rejection_tool_no_escalation():
    """Verify reject_patient_response does NOT escalate and stores critique."""
    ctx = DummyToolContext(state={"patient_draft": "The pharmacokinetic profile shows severe nephrotoxicity."})
    result = reject_patient_response(
        critique="Too complex; replace 'pharmacokinetic profile' with everyday words.",
        tool_context=ctx,
    )

    assert result["status"] == "rejected"
    assert ctx.actions.escalate is False
    assert ctx.state["approved"] is False
    assert "Too complex" in ctx.state["judge_critique"]


@pytest.mark.asyncio
async def test_in_memory_runner_session_lifecycle():
    """Verify InMemoryRunner session initialization and state management."""
    pipeline = build_pipeline(use_mcp=False)
    runner = InMemoryRunner(agent=pipeline, app_name="test_fda_agent")

    session = await runner.session_service.create_session(
        user_id="test_patient_user",
        app_name="test_fda_agent",
    )
    assert session is not None
    assert session.id is not None
    assert session.user_id == "test_patient_user"
    assert session.app_name == "test_fda_agent"

